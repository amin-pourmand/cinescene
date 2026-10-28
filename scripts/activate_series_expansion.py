"""Build a separate index generation, validate it, then install with rollback.

Studio must be stopped. All builds, snapshots and backups stay on the data drive.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import pickle
import shutil
import socket
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runtime_environment import configure_runtime
configure_runtime()
from core.model_worker import run_worker
from core.resource_budget import check_model_budget

CATALOG_FILES = ("tv_series_enriched.json", "tv_episodes_enriched.json", "episode_expansion_documents.json",
                 "episode_expansion_report.json", "cinescene_catalog.json")


def validate_candidate(candidate):
    series = json.loads((candidate / "tv_series_enriched.json").read_text(encoding="utf-8"))
    episodes = json.loads((candidate / "tv_episodes_enriched.json").read_text(encoding="utf-8"))
    parents = {str(row["id"]) for row in series}
    if len(parents) != len(series) or len({str(row["id"]) for row in episodes}) != len(episodes):
        raise ValueError("Candidate identities are duplicated")
    external = [str(row["external_tvmaze"]) for row in series if row.get("external_tvmaze")]
    if len(set(external)) != len(external):
        raise ValueError("Two series claim the same canonical TVmaze identity")
    from scripts.expand_episode_dataset import normalized_title
    for row in series:
        if not row.get("id_aliases"):
            continue
        proof = row.get("identity_evidence") or {}
        cast = {normalized_title(name) for name in row.get("cast", [])}
        overlap = {normalized_title(name) for name in proof.get("cast_overlap", [])}
        if not row.get("external_tvmaze") or proof.get("method") != "exact-title-and-main-cast" or str(proof.get("tvmaze")) != str(row["external_tvmaze"]) or len(cast & overlap) < 2:
            raise ValueError("Canonical aliases lack matching source/cast evidence")
        if set(map(str, row["id_aliases"])) & parents:
            raise ValueError("Canonical aliases overlap candidate identities")
    for episode in episodes:
        if str(episode.get("parent_id")) not in parents or episode.get("record_type") != "episode":
            raise ValueError("Episode has no valid parent series")
        if episode.get("scene_timeline") or episode.get("license") != "CC-BY-SA-4.0" or not episode.get("source_url", "").startswith("https://www.tvmaze.com/"):
            raise ValueError("Episode evidence lacks provenance or claims an invented timeline")
    return {"series": len(series), "episodes": len(episodes)}


def validate_indexes(folder, candidate=None):
    import faiss
    index = faiss.read_index(str(folder / "faiss_index_v2.bin"))
    with (folder / "metadata_v2.pkl").open("rb") as handle:
        metadata = pickle.load(handle)
    multi = faiss.read_index(str(folder / "multilingual.index"))
    keys = json.loads((folder / "multilingual_metadata.json").read_text(encoding="utf-8"))
    if index.ntotal != len(metadata) or multi.ntotal != len(keys) or index.d != 1024 or multi.d != 768:
        raise ValueError("Prepared index dimensions/counts are inconsistent")
    from multilingual_index import record_key
    with (folder / "scene_metadata.pkl").open("rb") as handle:
        scenes = pickle.load(handle)
    scene_index = faiss.read_index(str(folder / "scenes.index"))
    if scene_index.ntotal != len(scenes) or scene_index.d != index.d:
        raise ValueError("Prepared scene index dimensions/counts are inconsistent")
    scene_keys = {record_key(row) for row in scenes}
    known = {record_key(row) for row in metadata} | scene_keys
    if set(keys) - known:
        raise ValueError("Multilingual index contains unknown record identities")
    if known - set(keys):
        raise ValueError("Prepared records are missing multilingual evidence")
    if candidate is not None:
        expected = json.loads((candidate / "episode_expansion_documents.json").read_text(encoding="utf-8"))
        if {str(row["id"]) for row in expected} - {str(row["id"]) for row in metadata}:
            raise ValueError("Prepared index is missing candidate series or episode records")
    return {"title_episode_vectors": index.ntotal, "multilingual_vectors": multi.ntotal,
            "parent_titles": len({str(row.get("parent_id") or row["id"]) for row in metadata}),
            "episode_records": sum(row.get("record_type") == "episode" for row in metadata),
            "scene_records": len(scenes)}


def require_stopped(port):
    with socket.socket() as connection:
        connection.settimeout(1)
        if connection.connect_ex(("127.0.0.1", port)) == 0:
            raise RuntimeError(f"Stop Studio on port {port} before installing an index generation")


def install_generation(prepared, active, candidate, catalogs, backup, storage, catalog_files=CATALOG_FILES):
    # Check the final absolute targets before moving any generated directory.
    active, prepared, backup, candidate, catalogs, storage = [path.resolve() for path in
                                                            (active, prepared, backup, candidate, catalogs, storage)]
    if any(path == storage or storage not in path.parents for path in (active, prepared, backup, candidate, catalogs)):
        raise ValueError("Every activation target must stay inside the configured storage directory")
    paths = (active, prepared, backup)
    if any(left == right or left in right.parents or right in left.parents
           for i, left in enumerate(paths) for right in paths[i + 1:]):
        raise ValueError("Index build/backup destinations must be separate from the active index")
    if os.name == "nt" and len({path.drive.lower() for path in (active, prepared, backup)}) != 1:
        raise ValueError("Index activation requires the same storage volume for atomic directory renames")
    backups = backup / "catalogs"
    backups.mkdir(parents=True, exist_ok=True)
    if not catalog_files or any(Path(name).name != name for name in catalog_files):
        raise ValueError("Catalog files must be explicit leaf filenames")
    existing = {name for name in catalog_files if (catalogs / name).exists()}
    for name in catalog_files:
        if (catalogs / name).exists():
            shutil.copy2(catalogs / name, backups / name)
    moved = False
    try:
        active.rename(backup / "index")
        moved = True
        prepared.rename(active)
        for name in catalog_files:
            source = candidate / name
            temporary = catalogs / (name + ".installing")
            shutil.copy2(source, temporary)
            temporary.replace(catalogs / name)
    except Exception:
        if moved:
            if active.exists():
                active.rename(backup / "failed-generation")
            (backup / "index").rename(active)
        for name in catalog_files:
            if (backups / name).exists():
                shutil.copy2(backups / name, catalogs / name)
            elif name not in existing:
                (catalogs / name).unlink(missing_ok=True)
            (catalogs / (name + ".installing")).unlink(missing_ok=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", default="data/processed/series_expansion_candidate")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    candidate = Path(args.candidate).resolve()
    report = {"candidate": validate_candidate(candidate)}
    if args.validate_only:
        print(json.dumps(report, indent=2))
        return
    require_stopped(args.port)
    check_model_budget(required_mb=2048)
    active = (ROOT / "data/index").resolve()
    storage = Path(os.getenv("CINESCENE_STORAGE_ROOT", active.parent)).resolve()
    if os.name == "nt" and storage.drive.lower() == os.environ.get("SystemDrive", "C:").lower():
        raise RuntimeError("Index generations must not be built on the system drive")
    if shutil.disk_usage(storage).free < 2 * 1024 ** 3:
        raise RuntimeError("At least 2 GB of storage-drive headroom is required")
    generation = storage / "artifacts/index_generations" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    prepared, backup = generation / "prepared", generation / "previous"
    shutil.copytree(active, prepared)
    print(f"Preparing separate generation: {prepared}", flush=True)
    steps = [
        ("refresh_series_index.py", ["--index-dir", str(prepared), "--input", str(candidate / "tv_series_enriched.json")]),
        ("append_catalog_to_index.py", ["--index-dir", str(prepared), "--input", str(candidate / "episode_expansion_documents.json"), "--batch-size", "2"]),
        ("reconcile_index_identities.py", ["--index-dir", str(prepared), "--catalog", str(candidate / "episode_expansion_documents.json")]),
        ("append_multilingual_documents.py", ["--index-dir", str(prepared)]),
    ]
    for script, arguments in steps:
        print(f"Running {script} with a 2 GB worker commit cap", flush=True)
        run_worker({"kind": "index_script", "script": script, "args": arguments},
                   timeout=3600, required_mb=2048, memory_mb=2048)
    report["indexes"] = validate_indexes(prepared, candidate)
    require_stopped(args.port)
    install_generation(prepared, active, candidate, ROOT / "data/processed", backup, storage)
    report.update({"installed_at": datetime.now(timezone.utc).isoformat(), "backup": str(backup), "generation": str(generation)})
    (generation / "activation_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
