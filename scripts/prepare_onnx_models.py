"""Download pinned, quantized model artifacts without importing PyTorch."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runtime_environment import configure_runtime

configure_runtime()

MODELS = {
    "bge": "Xenova/bge-large-en-v1.5",
    "multilingual": "Xenova/multilingual-e5-base",
    "reranker": "Xenova/ms-marco-MiniLM-L-6-v2",
    "browser": "Xenova/multilingual-e5-small",
    "strong-reranker": "Xenova/bge-reranker-base",
    "compact-reranker": "mixedbread-ai/mxbai-rerank-xsmall-v1",
}
REVISIONS = {
    "bge": "dfeef6070b90658e1b391a6940efdb0925c1de6f",
    "multilingual": "1ec9243030a27d1a115d5c340572074c125b58b2",
    "reranker": "a09144355adeed5f58c8ed011d209bf8ee5a1fec",
    "browser": "761b726dd34fb83930e26aab4e9ac3899aa1fa78",
    "strong-reranker": "280bcc27a84e0b898c251e06fddb25171bd9b101",
    "compact-reranker": "b5c6e9da73abc3711f593f705371cdbe9e0fe422",
}
FILES = {"config.json", "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json", "onnx/model_quantized.onnx"}


def request(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "CineScene/1.0"}), timeout=120)


def checksum(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prepare(name: str):
    reference = MODELS[name]
    revision_path = "/revision/" + REVISIONS[name] if name in REVISIONS else ""
    with request(f"https://huggingface.co/api/models/{reference}{revision_path}?blobs=true") as response:
        metadata = json.load(response)
    revision = metadata["sha"]
    destination = (ROOT / "models" / "onnx" / reference.split("/")[-1]).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    downloads = []
    available = {item["rfilename"]: item for item in metadata["siblings"]}
    for filename in sorted(FILES & available.keys()):
        details = available[filename]
        expected_hash = details.get("lfs", {}).get("sha256")
        expected_size = details.get("lfs", {}).get("size") or details.get("size")
        target = destination / filename
        if target.exists() and (not expected_size or target.stat().st_size == expected_size):
            actual_hash = checksum(target)
            if not expected_hash or expected_hash == actual_hash:
                print(f"Verified: {name}/{filename}", flush=True)
                downloads.append({"file": filename, "bytes": target.stat().st_size, "sha256": actual_hash})
                continue
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".part")
        digest = hashlib.sha256()
        total = 0
        print(f"Downloading {reference}/{filename} -> {target}", flush=True)
        with request(f"https://huggingface.co/{reference}/resolve/{revision}/{filename}") as response, temporary.open("wb") as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                total += len(chunk)
                handle.write(chunk)
        if expected_size and total != expected_size:
            raise ValueError(f"Incomplete download: {filename}")
        if expected_hash and digest.hexdigest() != expected_hash:
            raise ValueError(f"Checksum mismatch: {filename}")
        temporary.replace(target)
        downloads.append({"file": filename, "bytes": total, "sha256": digest.hexdigest()})
    manifest = {"repository": reference, "revision": revision, "files": downloads}
    (destination / "artifact_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"name": name, "path": str(destination), "revision": revision}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("models", nargs="*", choices=list(MODELS), default=["bge", "multilingual", "reranker"])
    for model in parser.parse_args().models:
        prepare(model)
