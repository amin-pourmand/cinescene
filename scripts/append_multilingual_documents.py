"""Append only new record keys to the existing E5 index, preserving old vectors."""
import json
import pickle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runtime_environment import configure_runtime
configure_runtime()


def main():
    import faiss
    from core.onnx_models import OnnxEncoder
    from multilingual_index import record_key, title_passages
    folder = ROOT / "data/index"
    report_path = folder / "multilingual_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    path = folder / "multilingual.index"
    keys_path = folder / "multilingual_metadata.json"
    index = faiss.read_index(str(path))
    keys = json.loads(keys_path.read_text(encoding="utf-8"))
    if len(keys) != index.ntotal:
        raise ValueError("Existing multilingual keys and vectors differ")
    with (folder / "metadata_v2.pkl").open("rb") as handle:
        metadata = pickle.load(handle)
    known = set(keys)
    pending = [(record_key(row), text) for row in metadata if record_key(row) not in known for text in title_passages(row)]
    if not pending:
        print("No new multilingual documents")
        return
    model = OnnxEncoder(report["model"], 384)
    if index.d != model.get_sentence_embedding_dimension():
        raise ValueError("The active E5 model and index dimensions differ")
    for offset in range(0, len(pending), 4):
        batch = pending[offset:offset + 4]
        index.add(model.encode([text for _, text in batch], batch_size=4))
        keys.extend(key for key, _ in batch)
        if offset % 40 == 0:
            print(f"Embedded {min(offset + 4, len(pending))}/{len(pending)} new multilingual passages", flush=True)
    temp = path.with_suffix(".tmp")
    faiss.write_index(index, str(temp))
    temp.replace(path)
    temporary_keys = keys_path.with_suffix(".tmp")
    temporary_keys.write_text(json.dumps(keys), encoding="utf-8")
    temporary_keys.replace(keys_path)
    report.update({"vectors": index.ntotal, "titles": len(metadata), "incremental_vectors": len(pending),
                   "incremental_precision": "int8 ONNX documents"})
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"appended": len(pending), "vectors": index.ntotal}))


if __name__ == "__main__":
    main()
