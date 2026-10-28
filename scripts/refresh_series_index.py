"""Refresh changed series title vectors without re-encoding the full catalog.

Run with Studio stopped after expand_episode_dataset.py. Episode prose is not
changed here; query-time filters use the authoritative parent series genres.
"""
from __future__ import annotations

import json
import argparse
import pickle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runtime_environment import configure_runtime
configure_runtime()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-dir", default=str(ROOT / "data/index"))
    parser.add_argument("--input", default=str(ROOT / "data/processed/tv_series_enriched.json"))
    args = parser.parse_args()
    import faiss
    import numpy as np
    from build_index_v2 import IndexBuilderV2
    from core.onnx_models import OnnxEncoder
    from multilingual_index import record_key, title_passages

    folder = Path(args.index_dir)
    metadata = pickle.loads((folder / "metadata_v2.pkl").read_bytes())
    documents = json.loads(Path(args.input).read_text(encoding="utf-8"))
    by_id = {str(row["id"]): row for row in documents if row.get("overview_source") == "tvmaze"}
    builder = IndexBuilderV2.__new__(IndexBuilderV2)
    changes = []
    for i, row in enumerate(metadata):
        if row.get("record_type") == "episode" or str(row["id"]) not in by_id:
            continue
        replacement = builder.prepare_metadata([by_id[str(row["id"])]])[0]
        if any(replacement.get(key) != row.get(key) for key in ("overview", "genres", "year", "rich_text")):
            changes.append((i, replacement))
    if not changes:
        print("No changed series title records")
        return
    index = faiss.read_index(str(folder / "faiss_index_v2.bin"))
    vectors = index.reconstruct_n(0, index.ntotal)
    model = OnnxEncoder("Xenova/bge-large-en-v1.5", 256)
    encoded = model.encode([row["rich_text"] for _, row in changes], batch_size=4)
    del model
    for (i, row), vector in zip(changes, encoded):
        metadata[i] = row
        vectors[i] = vector
    updated = faiss.IndexFlatIP(index.d)
    updated.add(vectors)
    report_path = folder / "multilingual_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    old = faiss.read_index(str(folder / "multilingual.index"))
    keys = json.loads((folder / "multilingual_metadata.json").read_text(encoding="utf-8"))
    changed_keys = {record_key(row) for _, row in changes}
    keep = [i for i, key in enumerate(keys) if key not in changed_keys]
    pending = [(record_key(row), text) for _, row in changes for text in title_passages(row)]
    model = OnnxEncoder(report["model"], 384)
    encoded = model.encode([text for _, text in pending], batch_size=4)
    del model
    multilingual = faiss.IndexFlatIP(old.d)
    multilingual.add(np.stack([old.reconstruct(i) for i in keep]))
    multilingual.add(encoded)
    # Finish both model computations before replacing any active artifacts.
    for name in ("faiss_index_v2.bin", "movies.index"):
        temporary = folder / (name + ".tmp")
        faiss.write_index(updated, str(temporary))
        temporary.replace(folder / name)
    for name in ("metadata_v2.pkl", "metadata.pkl"):
        temporary = folder / (name + ".tmp")
        temporary.write_bytes(pickle.dumps(metadata))
        temporary.replace(folder / name)
    temporary = folder / "multilingual.tmp"
    faiss.write_index(multilingual, str(temporary))
    temporary.replace(folder / "multilingual.index")
    (folder / "multilingual_metadata.json").write_text(json.dumps([keys[i] for i in keep] + [key for key, _ in pending]), encoding="utf-8")
    report.update({"vectors": multilingual.ntotal, "refreshed_series": len(changes)})
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"refreshed_series": len(changes), "refreshed_passages": len(pending), "total_passages": multilingual.ntotal}))


if __name__ == "__main__":
    main()
