"""Build E5-small passage vectors with CPU int8 or offline CUDA float16."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.onnx_models import OnnxEncoder, model_folder
from core.public_retrieval import catalog_passages


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--resume", action="store_true", help="Resume an interrupted build for this unchanged catalog.")
    parser.add_argument("--runtime", choices=("onnx", "cuda"), default="onnx")
    parser.add_argument("--reuse", action="store_true", help="Reuse unchanged passage rows from an already complete index.")
    args = parser.parse_args()
    directory = ROOT / "data/index/passage_experiment"
    catalog = directory / "catalog.sample.json"
    items = json.loads(catalog.read_text(encoding="utf-8"))["items"]
    passages = catalog_passages(items)
    reference = "Xenova/multilingual-e5-small"
    manifest = json.loads((model_folder(reference) / "artifact_manifest.json").read_text())
    reuse, old_vectors, old_manifest = {}, None, None
    if args.reuse:
        if args.resume:
            raise ValueError("Choose either --reuse or --resume, not both.")
        old_manifest = json.loads((directory / "semantic-index.json").read_text(encoding="utf-8"))
        if old_manifest["revision"] != manifest["revision"] or old_manifest["catalog_sha256"] != hashlib.sha256(catalog.read_bytes()).hexdigest():
            raise ValueError("Reuse requires the same catalog and model revision.")
        old_vectors = np.fromfile(directory / "semantic-vectors.f32", dtype="<f4").reshape(-1, 384)
        reuse = {json.dumps(row, sort_keys=True): i for i, row in enumerate(old_manifest["passages"])}
    print(f"Encoding {len(passages)} passages for {len(items)} titles", flush=True)
    if args.runtime == "cuda":
        from runtime_environment import configure_runtime
        configure_runtime()
        import torch
        from tokenizers import Tokenizer
        from transformers import AutoModel
        print("Loading the local E5 checkpoint on CUDA", flush=True)
        network = AutoModel.from_pretrained(str(ROOT / "models/multilingual-e5-small"),
                                            local_files_only=True, torch_dtype=torch.float16).to("cuda").eval()
        tokenizer = Tokenizer.from_file(str(model_folder(reference) / "tokenizer.json"))
        tokenizer.enable_padding(pad_id=1, pad_token="<pad>")
        tokenizer.enable_truncation(max_length=256)

        class GPUEncoder:
            def encode(self, batch, **kwargs):
                encoded = tokenizer.encode_batch(batch)
                inputs = {"input_ids": torch.tensor([row.ids for row in encoded], device="cuda"),
                          "attention_mask": torch.tensor([row.attention_mask for row in encoded], device="cuda")}
                with torch.inference_mode():
                    hidden = network(**inputs).last_hidden_state.float()
                    mask = inputs["attention_mask"].unsqueeze(-1)
                    pooled = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1)
                    return torch.nn.functional.normalize(pooled, p=2, dim=1).cpu().numpy()
        model = GPUEncoder()
    else:
        model = OnnxEncoder(reference, max_length=256)
    target = directory / "semantic-vectors.f32"
    temporary = target.with_suffix(".partial")
    started = time.monotonic()
    checkpoint = directory / "semantic-build-checkpoint.json"
    signature = hashlib.sha256(catalog.read_bytes()).hexdigest()
    start_row = 0
    if args.resume and temporary.exists():
        if checkpoint.exists():
            previous = json.loads(checkpoint.read_text())
            if previous["catalog_sha256"] != signature or previous.get("runtime", "onnx") != args.runtime:
                raise ValueError("Cannot resume: the catalog or encoder runtime changed.")
        size = temporary.stat().st_size
        if size % (384 * 4):
            raise ValueError("Cannot resume: incomplete vector row.")
        start_row = size // (384 * 4)
    checkpoint.write_text(json.dumps({"catalog_sha256": signature, "runtime": args.runtime}), encoding="utf-8")
    with temporary.open("ab" if start_row else "wb") as output:
        for offset in range(start_row, len(passages), args.batch_size):
            rows = passages[offset:offset + args.batch_size]
            vectors = np.empty((len(rows), 384), dtype="<f4")
            missing = []
            for i, row in enumerate(rows):
                previous = reuse.get(json.dumps(row, sort_keys=True))
                if previous is None:
                    missing.append(i)
                else:
                    vectors[i] = old_vectors[previous]
            if missing:
                batch = ["passage: " + rows[i]["text"] for i in missing]
                vectors[missing] = model.encode(batch, batch_size=args.batch_size, normalize_embeddings=True, convert_to_numpy=True)
            vectors.tofile(output)
            if (offset - start_row) % (args.batch_size * 50) == 0:
                print(f"{offset}/{len(passages)}; {time.monotonic() - started:.0f}s", flush=True)
    temporary.replace(target)
    checkpoint.unlink(missing_ok=True)
    payload = {
        "version": 1, "model": reference, "revision": manifest["revision"],
        "dtype": "q8", "dimension": 384, "max_length": 256,
        "document_runtime": args.runtime, "document_precision": "float16" if args.runtime == "cuda" else "int8",
        "document_model": "intfloat/multilingual-e5-small" if args.runtime == "cuda" else reference,
        "reused_rows": len(reuse),
        "reused_document_precision": old_manifest.get("document_precision") if old_manifest else None,
        "pooling": "mean", "normalized": True, "query_prefix": "query: ",
        "catalog_sha256": hashlib.sha256(catalog.read_bytes()).hexdigest(),
        "vectors_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "titles": len(items), "passages": passages,
    }
    (directory / "semantic-index.json").write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Completed in {time.monotonic() - started:.1f}s; {target.stat().st_size:,} bytes", flush=True)


if __name__ == "__main__":
    main()
