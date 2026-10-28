"""Install a source-verified film expansion with staged indexes and rollback."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import hashlib
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runtime_environment import configure_runtime
configure_runtime()
from core.model_worker import run_worker
from core.resource_budget import check_model_budget
from scripts.activate_series_expansion import install_generation, require_stopped, validate_indexes

CATALOG_FILES = ("movies_enriched.json", "movie_expansion_documents.json", "movie_expansion_report.json", "cinescene_catalog.json")
INDEX_STATE_FILES = ("faiss_index_v2.bin", "metadata_v2.pkl", "multilingual.index", "multilingual_metadata.json",
                     "scenes.index", "scene_metadata.pkl", "index_report.json")


def index_fingerprint(folder):
    result = {}
    for name in INDEX_STATE_FILES:
        digest = hashlib.sha256()
        with (Path(folder) / name).open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        result[name] = digest.hexdigest()
    return result


def capture_source_generation(generation, active, verify_copy=False):
    state = index_fingerprint(active)
    if verify_copy and index_fingerprint(generation / "prepared") != state:
        raise ValueError("Prepared index is no longer an unchanged source copy")
    path = generation / "source_state.json"
    if path.exists():
        raise ValueError("Source fingerprint already exists")
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def validate_resume_generation(generation, storage, active):
    generation, generations = generation.resolve(), (storage / "artifacts/index_generations").resolve()
    if generation.parent != generations or not (generation / "prepared").is_dir() or (generation / "previous").exists():
        raise ValueError("Only an uninstalled staged generation inside storage can be resumed")
    state = json.loads((generation / "source_state.json").read_text(encoding="utf-8"))
    if state != index_fingerprint(active):
        raise ValueError("Active indexes changed since this generation was started")
    return generation


def validate_movie_candidate(candidate):
    load = lambda name: json.loads((candidate / name).read_text(encoding="utf-8"))
    movies, documents, report = load("movies_enriched.json"), load("movie_expansion_documents.json"), load("movie_expansion_report.json")
    identities = {str(row["id"]) for row in movies}
    if len(identities) != len(movies) or len({str(row["id"]) for row in documents}) != len(documents):
        raise ValueError("Duplicate film identities")
    if {str(row["id"]) for row in documents} - identities:
        raise ValueError("Candidate is missing changed films")
    if report.get("failures"):
        raise ValueError("Resolve source failures before activating the candidate")
    for row in documents:
        sources = row.get("evidence_sources", [])
        if row.get("media_type") != "movie" or not sources or not all(
            s.get("license") == "CC-BY-SA-4.0" and str(s.get("revision_url", "")).startswith("https://en.wikipedia.org/w/index.php?oldid=")
            and isinstance(s.get("revision_id"), int) for s in sources
        ):
            raise ValueError("Film story evidence lacks attributed revision provenance")
    combined = load("cinescene_catalog.json")
    if len({str(row["id"]) for row in combined}) != len(combined) or identities - {str(row["id"]) for row in combined}:
        raise ValueError("Combined catalog is incomplete or has duplicate identities")
    return {"movies": len(movies), "changed_movies": len(documents), "new_movies": report["new_movies"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", default="data/processed/movie_expansion_candidate")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--resume-generation", help="Reuse an uninstalled generation only when its active-source fingerprints still match")
    args = parser.parse_args()
    candidate = (ROOT / args.candidate).resolve()
    report = {"candidate": validate_movie_candidate(candidate)}
    if args.validate_only:
        print(json.dumps(report, indent=2))
        return
    require_stopped(args.port)
    check_model_budget(required_mb=2048)
    active = (ROOT / "data/index").resolve()
    storage = Path(os.environ["CINESCENE_STORAGE_ROOT"]).resolve()
    if os.name == "nt" and storage.drive.lower() == os.environ.get("SystemDrive", "C:").lower():
        raise ValueError("Index generations must stay off the system drive")
    if storage not in candidate.parents or shutil.disk_usage(storage).free < 3 * 1024 ** 3:
        raise ValueError("Candidate must stay in storage with at least 3 GB of free headroom")
    generation = (validate_resume_generation(Path(args.resume_generation), storage, active) if args.resume_generation else
                  storage / "artifacts/index_generations" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f"))
    prepared, backup = generation / "prepared", generation / "previous"
    if not args.resume_generation:
        shutil.copytree(active, prepared)
        capture_source_generation(generation, active)
    print(f"Preparing film generation: {generation}", flush=True)
    run_worker({"kind": "index_script", "script": "refresh_catalog_index.py",
                "args": ["--input", str(candidate / "movie_expansion_documents.json"), "--index-dir", str(prepared)]},
               timeout=7200, required_mb=2048, memory_mb=2048)
    report["indexes"] = validate_indexes(prepared)
    import pickle
    metadata = pickle.loads((prepared / "metadata_v2.pkl").read_bytes())
    before = pickle.loads((active / "metadata_v2.pkl").read_bytes())
    movies = json.loads((candidate / "movies_enriched.json").read_text(encoding="utf-8"))
    ids = {str(row["id"]) for row in metadata}
    if {str(row["id"]) for row in before + movies} - ids:
        raise ValueError("Prepared generation lost existing records or candidate films")
    from collections import Counter
    from multilingual_index import record_key, title_passages
    keys = Counter(json.loads((prepared / "multilingual_metadata.json").read_text(encoding="utf-8")))
    changed = {str(row["id"]) for row in json.loads((candidate / "movie_expansion_documents.json").read_text(encoding="utf-8"))}
    if any(keys[record_key(row)] != len(title_passages(row)) for row in metadata if str(row["id"]) in changed):
        raise ValueError("Updated film plot passages are not aligned with their multilingual vectors")
    require_stopped(args.port)
    install_generation(prepared, active, candidate, ROOT / "data/processed", backup, storage, CATALOG_FILES)
    report.update({"installed_at": datetime.now(timezone.utc).isoformat(), "generation": str(generation), "backup": str(backup)})
    (generation / "activation_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
