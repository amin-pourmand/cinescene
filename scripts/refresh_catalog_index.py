"""Refresh changed/new film records in a staged BGE/E5 generation only."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gc
import json
from pathlib import Path
import pickle
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runtime_environment import configure_runtime
configure_runtime()


def refresh_catalog(folder, documents, encoder_factory=None):
    import faiss
    import numpy as np
    from build_index_v2 import IndexBuilderV2
    from core.onnx_models import OnnxEncoder
    from core.resource_budget import check_model_budget
    from multilingual_index import record_key, title_passages
    factory = encoder_factory or OnnxEncoder
    folder = Path(folder)
    metadata = pickle.loads((folder / "metadata_v2.pkl").read_bytes())
    known = {str(row["id"]): i for i, row in enumerate(metadata)}
    if len(known) != len(metadata) or len({str(row["id"]) for row in documents}) != len(documents):
        raise ValueError("Duplicate catalog identities")
    builder = IndexBuilderV2.__new__(IndexBuilderV2)
    changes, e5_changes = [], []
    for document in documents:
        replacement = builder.prepare_metadata([document])[0]
        position = known.get(str(document["id"]))
        previous = metadata[position] if position is not None else None
        if position is None:
            position = len(metadata)
            metadata.append(replacement)
        elif metadata[position] == replacement:
            continue
        if metadata[position].get("record_type", "title") != "title":
            raise ValueError("Film refresh cannot replace episode/scene records")
        metadata[position] = replacement
        changes.append((position, replacement))
        if previous is None or title_passages(previous) != title_passages(replacement):
            e5_changes.append((position, replacement))
    if not changes:
        return {"changed_titles": 0}
    old = faiss.read_index(str(folder / "faiss_index_v2.bin"))
    bge = factory("Xenova/bge-large-en-v1.5", 256)
    vectors = np.zeros((len(metadata), old.d), dtype="float32")
    vectors[:old.ntotal] = old.reconstruct_n(0, old.ntotal)
    for offset in range(len(changes)):
        if offset % 20 == 0:
            check_model_budget(required_mb=0)
            print(f"BGE film refresh {offset}/{len(changes)}", flush=True)
        batch = changes[offset:offset + 1]
        encoded = bge.encode([row["rich_text"] for _, row in batch], batch_size=1)
        for (position, _), vector in zip(batch, encoded):
            vectors[position] = vector
    del bge
    gc.collect()
    updated = faiss.IndexFlatIP(old.d)
    updated.add(vectors)
    del old, vectors
    keys = json.loads((folder / "multilingual_metadata.json").read_text(encoding="utf-8"))
    multilingual = faiss.read_index(str(folder / "multilingual.index"))
    if len(keys) != multilingual.ntotal:
        raise ValueError("Multilingual identities and vector counts differ")
    changed_keys = {record_key(row) for _, row in e5_changes}
    keep = [i for i, key in enumerate(keys) if key not in changed_keys]
    refreshed = faiss.IndexFlatIP(multilingual.d) if e5_changes else multilingual
    if e5_changes:
        for offset in range(0, len(keep), 512):
            refreshed.add(np.stack([multilingual.reconstruct(i) for i in keep[offset:offset + 512]]))
        del multilingual
    report_path = folder / "multilingual_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    pending = [(record_key(row), text) for _, row in e5_changes for text in title_passages(row)]
    new_keys = [keys[i] for i in keep]
    if pending:
        e5 = factory(report["model"], 384)
        for offset in range(0, len(pending), 2):
            if offset % 40 == 0:
                check_model_budget(required_mb=0)
                print(f"E5 film evidence {offset}/{len(pending)}", flush=True)
            batch = pending[offset:offset + 2]
            refreshed.add(e5.encode([text for _, text in batch], batch_size=2))
            new_keys.extend(key for key, _ in batch)
        del e5
    gc.collect()
    # Nothing is written until both encoders have completed successfully.
    for name in ("faiss_index_v2.bin", "movies.index"):
        faiss.write_index(updated, str(folder / (name + ".tmp")))
        (folder / (name + ".tmp")).replace(folder / name)
    for name in ("metadata_v2.pkl", "metadata.pkl"):
        (folder / (name + ".tmp")).write_bytes(pickle.dumps(metadata))
        (folder / (name + ".tmp")).replace(folder / name)
    if e5_changes:
        faiss.write_index(refreshed, str(folder / "multilingual.index.tmp"))
        (folder / "multilingual.index.tmp").replace(folder / "multilingual.index")
        (folder / "multilingual_metadata.json").write_text(json.dumps(new_keys), encoding="utf-8")
    report.update({"vectors": refreshed.ntotal, "titles": len(metadata), "refreshed_movie_titles": len(e5_changes),
                   "title_vectors": sum(not key.startswith("scene:") for key in new_keys),
                   "scene_vectors": sum(key.startswith("scene:") for key in new_keys)})
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    main_report_path = folder / "index_report.json"
    main_report = json.loads(main_report_path.read_text(encoding="utf-8"))
    main_report.update({"movies_indexed": len(metadata), "refreshed_movie_titles": len(changes),
                        "generation_id": datetime.now(timezone.utc).isoformat(),
                        "document_policy": "narrative-first-v1", "document_batch_size": 1})
    main_report_path.write_text(json.dumps(main_report, indent=2), encoding="utf-8")
    return {"changed_titles": len(changes), "title_episode_vectors": updated.ntotal,
            "refreshed_story_passages": len(pending), "multilingual_vectors": refreshed.ntotal}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--index-dir", required=True)
    args = parser.parse_args()
    folder = Path(args.index_dir).resolve()
    if folder == (ROOT / "data/index").resolve():
        raise ValueError("Refusing in-place updates; use activate_movie_expansion.py")
    print(json.dumps(refresh_catalog(folder, json.loads(Path(args.input).read_text(encoding="utf-8"))), indent=2))


if __name__ == "__main__":
    main()
