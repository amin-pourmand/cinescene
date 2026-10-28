"""Short-lived inference workers; model buffers leave memory when the worker exits."""
from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys

from core.resource_budget import check_model_budget


ROOT = Path(__file__).resolve().parents[1]


class ModelWorkerError(RuntimeError):
    def __init__(self, message, diagnostic=""):
        super().__init__(message)
        self.diagnostic = diagnostic


def worker_launch(module, executable=None):
    environment = {**os.environ, "PYTHONUTF8": "1", "PYTHONUNBUFFERED": "1",
                   "TOKENIZERS_PARALLELISM": "false", "OMP_NUM_THREADS": "2", "CT2_PACKED_GEMM": "0"}
    if os.name == "nt":
        # Windows venv launchers spawn another Python process. Launch the real
        # interpreter directly so the job cap cannot miss that child in a race.
        prefix = Path(executable).parents[1] if executable else Path(sys.prefix)
        packages = prefix / "Lib/site-packages"
        environment["PYTHONPATH"] = os.pathsep.join((str(ROOT), str(packages.resolve())))
        command = [sys._base_executable, "-S", "-m", module]
    else:
        command = [str(executable or sys.executable), "-m", module]
    return command, environment


class WorkerJob:
    """Windows job: bound worker commit and kill descendants on timeout/closure."""

    def __init__(self, process, memory_mb=None):
        self.handle = None
        if os.name != "nt":
            return
        from ctypes import wintypes as w

        class BasicLimits(ctypes.Structure):
            _fields_ = [("process_time", ctypes.c_longlong), ("job_time", ctypes.c_longlong),
                        ("flags", w.DWORD), ("min_working_set", ctypes.c_size_t),
                        ("max_working_set", ctypes.c_size_t), ("active_processes", w.DWORD),
                        ("affinity", ctypes.c_size_t), ("priority", w.DWORD), ("scheduling", w.DWORD)]

        class IoCounters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in ("read_ops", "write_ops", "other_ops", "read_bytes", "write_bytes", "other_bytes")]

        class ExtendedLimits(ctypes.Structure):
            _fields_ = [("basic", BasicLimits), ("io", IoCounters),
                        ("process_memory", ctypes.c_size_t), ("job_memory", ctypes.c_size_t),
                        ("peak_process_memory", ctypes.c_size_t), ("peak_job_memory", ctypes.c_size_t)]

        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
        self.kernel.CreateJobObjectW.restype = w.HANDLE
        self.kernel.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
        self.kernel.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
        self.kernel.CloseHandle.argtypes = [w.HANDLE]
        self.handle = self.kernel.CreateJobObjectW(None, None)
        limits = ExtendedLimits()
        limits.basic.flags = 0x2000 | 0x200  # KILL_ON_JOB_CLOSE | JOB_MEMORY
        limits.job_memory = (memory_mb or int(os.getenv("CINESCENE_WORKER_MEMORY_MB", "1536"))) * 1024 ** 2
        if not self.handle or not self.kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)) or not self.kernel.AssignProcessToJobObject(self.handle, int(process._handle)):
            self.close()
            raise RuntimeError("Could not establish the model worker memory limit; inference was not started.")

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def run_worker(payload, executable=None, timeout=120, required_mb=768, memory_mb=None):
    check_model_budget(required_mb)
    command, environment = worker_launch("core.model_worker", executable)
    process = subprocess.Popen(command, cwd=ROOT,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, encoding="utf-8", env=environment,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    job = None
    try:
        job = WorkerJob(process, memory_mb=memory_mb)
        output, errors = process.communicate(json.dumps(payload, ensure_ascii=True), timeout=timeout)
        if process.returncode:
            # Do not log private query text or model inputs in a persistent file.
            raise ModelWorkerError(f"Model worker failed (exit {process.returncode}); memory limit or inference failure.", errors[-2000:])
        result = json.loads(output)
        if not isinstance(result, dict):
            raise ModelWorkerError("The model worker returned an invalid response.")
        if "error" in result:
            raise ModelWorkerError("Model inference could not finish.", str(result["error"]))
        return result["value"]
    except subprocess.TimeoutExpired as exc:
        raise ModelWorkerError("Model processing timed out; the worker was stopped.") from exc
    except (json.JSONDecodeError, KeyError) as exc:
        raise ModelWorkerError("The model worker returned an invalid response.") from exc
    finally:
        if job:
            job.close()
        if process.poll() is None:
            process.kill()
            process.communicate()


def main():
    from runtime_environment import configure_runtime
    configure_runtime()
    # The parent assigns the memory-limited job before sending any input.
    payload = json.load(sys.stdin)
    if payload["kind"] == "translate":
        from core.query_translation import translate_local
        value = translate_local(payload["model"], payload["text"], truncate=payload.get("truncate", False))
    elif payload["kind"] == "profile":
        from core.resource_budget import process_memory
        value = {"initial": process_memory()}
        import numpy
        value["numpy"] = process_memory()
        from hybrid_search import HybridSearchEngine
        value["imports"] = process_memory()
        # Engine startup prints status; keep the worker's stdout protocol clean.
        from contextlib import redirect_stdout
        with redirect_stdout(sys.stderr):
            engine = HybridSearchEngine(enable_reranker=False)
        value["engine"] = process_memory()
        value["titles"] = engine.status()["movies"]
    elif payload["kind"] == "scene_refresh":
        from contextlib import redirect_stdout
        from scene_index import build_scene_index
        from multilingual_index import INDEX_PATH, build_multilingual_index
        with redirect_stdout(sys.stderr):
            value = build_scene_index(model_path=payload["model"], batch_size=2)
            if INDEX_PATH.exists():
                value["multilingual"] = build_multilingual_index(scene_only=True, batch_size=2)
    elif payload["kind"] == "index_script":
        import runpy
        from contextlib import redirect_stdout
        allowed = {"refresh_series_index.py", "refresh_catalog_index.py", "append_catalog_to_index.py", "append_multilingual_documents.py", "reconcile_index_identities.py", "build_browser_index.py"}
        if payload["script"] not in allowed:
            raise ValueError("Unknown index preparation script")
        sys.argv = [payload["script"], *payload.get("args", [])]
        with redirect_stdout(sys.stderr):
            runpy.run_path(str(ROOT / "scripts" / payload["script"]), run_name="__main__")
        value = {"completed": payload["script"]}
    else:
        from core.onnx_models import OnnxEncoder, OnnxReranker
        if payload["kind"] == "embed":
            model = OnnxEncoder(payload["model"], payload["max_length"])
            value = model.encode(payload["texts"], batch_size=1).tolist()
        elif payload["kind"] == "rerank":
            model = OnnxReranker(payload["model"], payload["max_length"])
            value = model.predict(payload["pairs"], batch_size=2).tolist()
        else:
            raise ValueError("Unknown model worker operation")
    print(json.dumps({"value": value}, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()
