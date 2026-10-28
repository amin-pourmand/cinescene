"""Remove proven duplicate title identities from a stopped/staged index generation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import pickle
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runtime_environment import configure_runtime
configure_runtime()


def reconcile_indexes(folder, documents):
    aliases = {}
    identities = {str(row["id"]) for row in documents}
    for row in documents:
        for alias in row.get("id_aliases", []):
            alias, target = str(alias), str(row["id"])
            if alias in identities or (alias in aliases and aliases[alias] != target):
                raise ValueError("Conflicting canonical identity aliases")
            aliases[alias] = target
    if not aliases:
        return {"removed_title_records": 0, "reparented_episodes": 0}
    import faiss
    from multilingual_index import record_key
    with (folder / "metadata_v2.pkl").open("rb") as handle:
        original = pickle.load(handle)
    indexed = {str(row["id"]) for row in original}
    if set(aliases.values()) - indexed:
        raise ValueError("Canonical targets must be indexed before removing their aliases")
    keep, metadata, dropped, reparented = [], [], set(), 0
    for i, row in enumerate(original):
        if str(row["id"]) in aliases and row.get("record_type") != "episode":
            dropped.add(record_key(row))
            continue
        row = dict(row)
        if str(row.get("parent_id")) in aliases:
            row["parent_id"] = aliases[str(row["parent_id"])]
            reparented += 1
        keep.append(i)
        metadata.append(row)
    if not dropped and not reparented:
        return {"removed_title_records": 0, "reparented_episodes": 0}
    index = faiss.read_index(str(folder / "faiss_index_v2.bin"))
    keys = json.loads((folder / "multilingual_metadata.json").read_text(encoding="utf-8"))
    multi = faiss.read_index(str(folder / "multilingual.index"))
    if index.ntotal != len(original) or multi.ntotal != len(keys):
        raise ValueError("Index counts differ before identity reconciliation")
    updated = faiss.IndexFlatIP(index.d)
    updated.add(index.reconstruct_n(0, index.ntotal)[keep])
    positions = [i for i, key in enumerate(keys) if key not in dropped]
    multilingual = faiss.IndexFlatIP(multi.d)
    multilingual.add(multi.reconstruct_n(0, multi.ntotal)[positions])
    for name, value in (("faiss_index_v2.bin", updated), ("movies.index", updated), ("multilingual.index", multilingual)):
        temporary = folder / (name + ".tmp")
        faiss.write_index(value, str(temporary))
        temporary.replace(folder / name)
    for name in ("metadata_v2.pkl", "metadata.pkl"):
        temporary = folder / (name + ".tmp")
        temporary.write_bytes(pickle.dumps(metadata))
        temporary.replace(folder / name)
    keys = [keys[i] for i in positions]
    (folder / "multilingual_metadata.json").write_text(json.dumps(keys), encoding="utf-8")
    report_path = folder / "multilingual_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    scenes = sum(key.startswith("scene:") for key in keys)
    report.update({"titles": len(metadata), "vectors": multilingual.ntotal, "title_vectors": multilingual.ntotal - scenes,
                   "scene_vectors": scenes, "identity_aliases": aliases})
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report_path = folder / "index_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report.update({"movies_indexed": len(metadata), "identity_aliases": aliases})
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return {"removed_title_records": len(original) - len(metadata), "reparented_episodes": reparented}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-dir", required=True)
    parser.add_argument("--catalog", required=True)
    args = parser.parse_args()
    print(json.dumps(reconcile_indexes(Path(args.index_dir), json.loads(Path(args.catalog).read_text(encoding="utf-8")))))


if __name__ == "__main__":
    main()
