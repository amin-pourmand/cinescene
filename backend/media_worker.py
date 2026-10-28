"""Keep optional speech/vision model memory out of the long-lived API process."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from core.model_worker import WorkerJob, worker_launch
from core.resource_budget import check_model_budget


ROOT = Path(__file__).resolve().parents[1]
PREFIX = "CINESCENE_EVENT:"


def crawl_in_worker(root, progress_callback=None, **options):
    heavy = options.get("enable_vision") or options.get("transcribe_audio")
    limit = int(os.getenv("CINESCENE_MEDIA_WORKER_MEMORY_MB", "3072")) if heavy else 1024
    check_model_budget(required_mb=limit if heavy else 384)
    log_dir = ROOT / "data/processed/worker_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log = log_dir / f"analysis-{uuid4().hex}.log"
    command, environment = worker_launch("backend.media_worker")
    with log.open("w", encoding="utf-8") as errors:
        process = subprocess.Popen(command, cwd=str(ROOT),
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors,
                                   text=True, encoding="utf-8", env=environment,
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        report, job = None, None
        try:
            job = WorkerJob(process, memory_mb=limit)
            process.stdin.write(json.dumps({"root": str(root), "options": options}) + "\n")
            process.stdin.close()
            for line in process.stdout:
                if not line.startswith(PREFIX):
                    continue
                event = json.loads(line[len(PREFIX):])
                if event["type"] == "report":
                    report = event["value"]
                elif event["type"] == "progress" and progress_callback:
                    progress_callback(event["value"])
            code = process.wait()
        finally:
            if job:
                job.close()
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            process.stdout.close()
        if code or report is None:
            raise RuntimeError(f"Video analysis worker failed (exit {code}). Diagnostics: {log}")
        return report


def main():
    from runtime_environment import configure_runtime
    configure_runtime()
    from ingestion.offline_video import crawl_offline_videos

    payload = json.loads(sys.stdin.readline())

    def emit(kind, value):
        print(PREFIX + json.dumps({"type": kind, "value": value}, ensure_ascii=True), flush=True)

    report = crawl_offline_videos(payload["root"], progress_callback=lambda event: emit("progress", event), **payload["options"])
    emit("report", report)


if __name__ == "__main__":
    main()
