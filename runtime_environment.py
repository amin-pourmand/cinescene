"""Configure project-local caches before importing model libraries."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv


def configure_runtime():
    root = Path(__file__).resolve().parent
    load_dotenv(root / ".env", override=False)
    # Set BLAS limits before NumPy/FAISS imports, not just ONNX session threads.
    # OpenBLAS thread buffers can otherwise dwarf the model's own allocation.
    threads = str(max(1, min(4, int(os.getenv("CINESCENE_CPU_THREADS", "2")))))
    for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ.setdefault(name, threads)
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    storage_root = os.getenv("CINESCENE_STORAGE_ROOT")
    if not storage_root:
        return
    storage = Path(storage_root)
    cache = storage / "cache"
    defaults = {
        "HF_HOME": cache / "huggingface",
        "HF_HUB_CACHE": cache / "huggingface" / "hub",
        "PIP_CACHE_DIR": cache / "pip",
        "TORCH_HOME": cache / "torch",
        "TORCH_EXTENSIONS_DIR": cache / "torch-extensions",
        "TORCHINDUCTOR_CACHE_DIR": cache / "torch-inductor",
        "CUDA_CACHE_PATH": cache / "cuda",
        "TRITON_CACHE_DIR": cache / "triton",
        "XDG_CACHE_HOME": cache,
        "TEMP": cache / "tmp",
        "TMP": cache / "tmp",
    }
    for name, path in defaults.items():
        path.mkdir(parents=True, exist_ok=True)
        if name in {"TEMP", "TMP"}:
            os.environ[name] = str(path)
        else:
            os.environ.setdefault(name, str(path))
    # Multipart uploads also use this location after their in-memory spool fills.
    tempfile.tempdir = str(defaults["TEMP"])
