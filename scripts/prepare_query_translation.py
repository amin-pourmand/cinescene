"""Prepare a pinned, offline research translator and a torch-free worker environment."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runtime_environment import configure_runtime
configure_runtime()
from core.query_translation import MODEL, translation_python
from scripts.prepare_onnx_models import checksum, request

REPOSITORY = "JustFrederik/nllb-200-distilled-600M-ct2-int8"
REVISION = "302d78f00e6fdb50a1064059df7c392b735e9d05"
FILES = {"config.json", "model.bin", "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json", "README.md", "shared_vocabulary.txt"}


def main():
    destination = MODEL.resolve()
    executable = translation_python().resolve()
    runtime = executable.parents[1]
    if os.name == "nt":
        system = os.environ.get("SystemDrive", "C:").lower()
        if any(path.drive.lower() == system for path in (destination, runtime)):
            raise RuntimeError("Set CINESCENE_STORAGE_ROOT and relocate models off the system drive before preparing translation.")
    destination.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(destination).free < 2 * 1024 ** 3:
        raise RuntimeError("At least 2 GB of free space is required on the model-storage drive.")
    with request(f"https://huggingface.co/api/models/{REPOSITORY}/revision/{REVISION}?blobs=true") as response:
        metadata = json.load(response)
    available = {row["rfilename"]: row for row in metadata["siblings"]}
    manifest = {"repository": REPOSITORY, "revision": REVISION, "upstream": "facebook/nllb-200-distilled-600M",
                "license": "CC-BY-NC-4.0", "purpose": "Noncommercial university research; not a production translation guarantee", "files": []}
    for name in sorted(FILES):
        details = available[name]
        target = destination / name
        size = details.get("lfs", {}).get("size") or details.get("size")
        expected = details.get("lfs", {}).get("sha256")
        valid = target.is_file() and target.stat().st_size == size and (not expected or checksum(target) == expected)
        if not valid:
            temporary = target.with_suffix(target.suffix + ".part")
            print(f"Downloading {name} ({size} bytes) to {destination}", flush=True)
            with request(f"https://huggingface.co/{REPOSITORY}/resolve/{REVISION}/{name}") as response, temporary.open("wb") as handle:
                shutil.copyfileobj(response, handle, length=1024 * 1024)
            if temporary.stat().st_size != size or (expected and checksum(temporary) != expected):
                raise RuntimeError(f"Artifact verification failed: {name}")
            temporary.replace(target)
        manifest["files"].append({"name": name, "bytes": target.stat().st_size, "sha256": checksum(target)})
    (destination / "artifact_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if not executable.is_file():
        venv.EnvBuilder(with_pip=True).create(runtime)
    subprocess.run([str(executable), "-m", "pip", "install", "--disable-pip-version-check",
                    "ctranslate2==4.8.1", "tokenizers==0.22.2", "python-dotenv>=1,<2", "numpy>=1.26,<2"], check=True)
    subprocess.run([str(executable), "-c", "import importlib.util; assert importlib.util.find_spec('torch') is None; import ctranslate2,tokenizers; print('Translation runtime ready; PyTorch is not installed.')"], check=True)
    print(json.dumps({"model": str(destination), "runtime": str(runtime), "revision": REVISION}), flush=True)


if __name__ == "__main__":
    main()
