"""Configure project-local caches before importing model libraries."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv


def configure_runtime():
    root = Path(__file__).resolve().parent
    load_dotenv(root / ".env", override=False)
    storage_root = os.getenv("CINESCENE_STORAGE_ROOT")
    if not storage_root:
        return
    storage = Path(storage_root)
    cache = storage / "cache"
    defaults = {"HF_HOME": cache / "huggingface", "HF_HUB_CACHE": cache / "huggingface" / "hub",
                "PIP_CACHE_DIR": cache / "pip", "TEMP": cache / "tmp", "TMP": cache / "tmp"}
    for name, path in defaults.items():
        path.mkdir(parents=True, exist_ok=True)
        if name in {"TEMP", "TMP"}:
            os.environ[name] = str(path)
        else:
            os.environ.setdefault(name, str(path))
    # Multipart uploads also use this location after their in-memory spool fills.
    tempfile.tempdir = str(defaults["TEMP"])
