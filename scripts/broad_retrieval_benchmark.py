"""Sequential HTTP diagnostics: bilingual retrieval, coverage and input handling.

No model weights are loaded here. Checkpoints contain only query labels and
result identities, never private video paths, transcripts or full API responses.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import pickle
import shutil
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runtime_environment import configure_runtime
configure_runtime()
from evaluation_metrics import expected_rank, normalize_title, summarize


def expand_cases(suite):
    cases = []
    for number, topic in enumerate(suite["topics"], 1):
        for language in ("en", "fa"):
            cases.append({"id": f"pair-{number:03}-{language}", "pair": f"pair-{number:03}",
                          "kind": "retrieval", "language": language,
                          "category": f"{topic['target_type']}_plot", "provenance": "manual",
                          "query": topic[language], "expected": [topic["title"]],
                          "expected_ids": [str(topic["target_id"])], "target_type": topic["target_type"]})
    for case in suite.get("additional", []):
        cases.append({"kind": "retrieval", "provenance": "manual", **case})
    for number, case in enumerate(suite.get("coverage", []), 1):
        cases.append({"id": f"coverage-{number:02}", "kind": "coverage", "language": "en", **case})
    cases.extend(suite.get("probes", []))
    if len({case["id"] for case in cases}) != len(cases):
        raise ValueError("Case IDs must be unique")
    return cases


def coverage_matches(case, catalog):
    names = {normalize_title(name) for name in [case["title"], *case.get("aliases", [])]}
    candidates = [row for row in catalog if normalize_title(row["title"]) in names
                  and row.get("media_type", "movie") == case["target_type"]]
    # Movie dates are canonical TMDB dates. Provider-series dates can instead
    # refer to a platform catalog, so do not infer series absence from that year.
    exact = [row for row in candidates if case["target_type"] != "movie" or str(row.get("year")) == case["year"]]
    return exact, candidates


def select_cases(cases, kinds=None, categories=None):
    selected = [case for case in cases if (not kinds or case["kind"] in kinds)
                and (not categories or case.get("category") in categories)]
    if not selected:
        raise ValueError("The requested selection contains no cases")
    return selected


def resolve_case_identities(cases, aliases):
    def canonical(identity):
        seen = set()
        identity = str(identity)
        while identity in aliases:
            if identity in seen:
                raise ValueError("Canonical identity aliases contain a cycle")
            seen.add(identity)
            identity = str(aliases[identity])
        return identity
    resolved = []
    for case in cases:
        row = dict(case)
        if case.get("expected_ids"):
            row["expected_ids"] = [canonical(value) for value in case["expected_ids"]]
            if row["expected_ids"] != list(map(str, case["expected_ids"])):
                row["original_expected_ids"] = case["expected_ids"]
        resolved.append(row)
    return resolved


def validate_targets(cases, catalog):
    by_id = {str(row["id"]): row for row in catalog if row.get("record_type") != "episode"}
    episodes = {(str(row.get("parent_id")), row.get("season"), row.get("episode")) for row in catalog
                if row.get("record_type") == "episode"}
    for case in cases:
        if case["kind"] != "retrieval":
            continue
        for target in case["expected_ids"]:
            if str(target) not in by_id:
                raise ValueError(f"Unknown target ID in {case['id']}: {target}")
            row = by_id[str(target)]
            if normalize_title(row["title"]) not in {normalize_title(name) for name in case["expected"]}:
                raise ValueError(f"Title/ID disagreement in {case['id']}")
            if case.get("target_type") and row.get("media_type", "movie") != case["target_type"]:
                raise ValueError(f"Wrong target media type in {case['id']}")
            if case.get("episode") is not None and (str(target), case["season"], case["episode"]) not in episodes:
                raise ValueError(f"Episode absent from available evidence: {case['id']}")


def result_identity(item):
    episode = item.get("matched_episode") or {}
    return {"id": str(item.get("id")), "title": str(item.get("title") or ""),
            "year": item.get("year"), "media_type": item.get("media_type", "movie"),
            "matched_episode": {key: episode.get(key) for key in ("season", "episode")} if episode else None}


def judge_probe(kind, status, results):
    if kind == "invalid":
        return status == 422
    if kind == "negative":
        return status == 422 or (status == 200 and not results)
    if kind == "ambiguous":
        return status == 200 and len(results) >= 2 and len({row["id"] for row in results}) == len(results)
    return None


def execute_case(client, case, catalog):
    payload = {"query": case.get("query", ""), "top_k": 10, "use_reranking": True}
    payload.update({key: case[key] for key in ("media_type", "scope") if key in case})
    exact, versions = [], []
    if case["kind"] == "invalid":
        payload = dict(case["payload"])
        if "query_repeat" in payload:
            payload["query"] = "x" * int(payload.pop("query_repeat"))
    elif case["kind"] == "coverage":
        exact, versions = coverage_matches(case, catalog)
        payload["media_type"] = case["target_type"]
        if case["target_type"] == "movie":
            payload["query"] += f" released in {case['year']}"
    started = time.perf_counter()
    results, error, status, interpretation = [], None, 0, {}
    try:
        response = client.post("/api/search", json=payload)
        status = response.status_code
        if status == 200:
            body = response.json()
            results = [result_identity(item) for item in body["results"]]
            interpretation = {key: body.get("interpretation", {}).get(key) for key in ("language", "translation", "translated_query", "warning")}
        elif status != 422:
            error = f"HTTP {status}"
    except Exception as exc:
        error = type(exc).__name__
    row = {"id": case["id"], "kind": case["kind"], "category": case.get("category"),
           "language": case.get("language"), "provenance": case.get("provenance"), "pair": case.get("pair"),
           "query": payload.get("query"), "expected": case.get("expected"),
           "expected_ids": case.get("expected_ids"), "status": status, "error": error,
           "original_expected_ids": case.get("original_expected_ids"),
           "latency_sec": round(time.perf_counter() - started, 3),
           "results": results, "rank": None,
           "interpretation": interpretation,
           "options": {key: payload[key] for key in ("media_type", "scope", "top_k") if key in payload}}
    if case["kind"] == "retrieval":
        row["rank"] = expected_rank(results, case)
        row["season"], row["episode"] = case.get("season"), case.get("episode")
        if case.get("episode") is not None:
            parent_only = {key: value for key, value in case.items() if key not in {"season", "episode"}}
            row["parent_rank"] = expected_rank(results, parent_only)
    elif case["kind"] == "coverage":
        row.update({"expected": [case["title"]], "requested_year": case["year"],
                    "catalog_present": bool(exact), "catalog_matches": exact, "other_versions": versions,
                    "rank": expected_rank(results, {"expected": [case["title"]], "expected_ids": [item["id"] for item in exact]}) if exact else None,
                    "returned_results_for_missing_target": not exact and status == 200 and bool(results)})
    else:
        row["passed"] = not error and judge_probe(case["kind"], status, results)
    return row


def report_metrics(rows):
    retrieval = [row for row in rows if row["kind"] == "retrieval"]
    groups = {field: {value: summarize([row for row in retrieval if row[field] == value])
                      for value in sorted({row[field] for row in retrieval if row[field]})}
              for field in ("language", "category", "provenance")}
    paired = {}
    for row in retrieval:
        if row["pair"]:
            paired.setdefault(row["pair"], {})[row["language"]] = row["rank"]
    complete = [pair for pair in paired.values() if "en" in pair and "fa" in pair]
    coverage = [row for row in rows if row["kind"] == "coverage"]
    return {"retrieval": summarize(retrieval), "by_language": groups["language"], "by_category": groups["category"],
            "by_provenance": groups["provenance"],
            "paired_topics": {"complete_pairs": len(complete),
                              "both_first": sum(pair["en"] == pair["fa"] == 1 for pair in complete),
                              "english_only_first": sum(pair["en"] == 1 and pair["fa"] != 1 for pair in complete),
                              "persian_only_first": sum(pair["fa"] == 1 and pair["en"] != 1 for pair in complete),
                              "neither_first": sum(pair["en"] != 1 and pair["fa"] != 1 for pair in complete)},
            "coverage": {"requests": len(coverage), "present": sum(row["catalog_present"] for row in coverage),
                         "missing": [row["expected"][0] for row in coverage if not row["catalog_present"]],
                         "nonempty_results_for_missing": sum(row["returned_results_for_missing_target"] for row in coverage)},
            "probes": {kind: {"cases": len(selected := [row for row in rows if row["kind"] == kind]),
                              "passed": sum(row["passed"] for row in selected)}
                       for kind in ("negative", "ambiguous", "invalid")},
            "technical_errors": sum(bool(row["error"]) for row in rows),
            "degraded_retrieval": sum(bool(row.get("interpretation", {}).get("warning")) for row in retrieval),
            "retrieval_non_200": sum(row["status"] != 200 for row in retrieval),
            "retrieval_p50_sec": round(statistics.median([row["latency_sec"] for row in retrieval]), 3) if retrieval else None,
            "retrieval_p95_sec": round(sorted(row["latency_sec"] for row in retrieval)[max(0, int(len(retrieval) * .95) - 1)], 3) if retrieval else None}


def engine_fingerprint(status):
    return {key: status.get(key) for key in ("fusion_version", "index_generation", "model", "precision", "embedding_dimension", "index_vectors", "multilingual_vectors", "reranker", "reranker_model", "identity_aliases")}


def check_system_space(min_free_gb, root=None):
    if min_free_gb > 0 and shutil.disk_usage(root or Path.home().anchor or "/").free < min_free_gb * 1024 ** 3:
        raise RuntimeError("System-drive free space fell below the limit; checkpoint preserved. Stop or free project-owned space before resuming.")


def write_report(output, suite, digest, start_status, end_status, planned, rows):
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "description": suite["description"],
              "suite_sha256": digest, "planned_inputs": planned, "completed_inputs": len(rows),
              "engine": start_status, "engine_unchanged": start_status == end_status if end_status is not None else None,
              "transport": "http; one request at a time; reranking enabled", "evaluation_version": "broad-v1",
              "identity_resolution": suite.get("identity_resolution", {}),
              "limitations": "Manual diagnostic sample, not a population estimate or independent held-out dataset. Episode checks are source-informed. Coverage/probes are excluded from retrieval metrics. Timing reflects this host, not a controlled load test.",
              **report_metrics(rows), "rows": rows}
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main():
    import httpx
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", default="benchmarks/broad-scenarios.json")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", default=str(Path(os.getenv("CINESCENE_STORAGE_ROOT", ROOT)) / "artifacts/broad-latest.json"), help="Raw local output; use summarize_broad_benchmark.py --public-json before publication")
    parser.add_argument("--kinds", nargs="+", choices=("retrieval", "coverage", "negative", "ambiguous", "invalid"))
    parser.add_argument("--categories", nargs="+", help="Select explicit retrieval categories for a focused regression run.")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--min-system-free-gb", type=float, default=2.0, help="Pause before the next request if system-drive space is low; 0 disables the guard.")
    args = parser.parse_args()
    case_file = Path(args.cases)
    suite = json.loads(case_file.read_text(encoding="utf-8"))
    digest = hashlib.sha256(case_file.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    cases = select_cases(expand_cases(suite), args.kinds, args.categories)
    if args.kinds or args.categories:
        selection = {"kinds": sorted(args.kinds or []), "categories": sorted(args.categories or [])}
        digest = hashlib.sha256((digest + json.dumps(selection, sort_keys=True)).encode()).hexdigest()
        suite["description"] += " Focused selection: " + json.dumps(selection, sort_keys=True) + "."
    with (ROOT / "data/index/metadata_v2.pkl").open("rb") as handle:
        catalog = [{key: row.get(key) for key in ("id", "title", "year", "media_type", "record_type", "parent_id", "season", "episode")}
                   for row in pickle.load(handle)]
    aliases = json.loads((ROOT / "data/index/index_report.json").read_text(encoding="utf-8")).get("identity_aliases", {})
    cases = resolve_case_identities(cases, aliases)
    suite["identity_resolution"] = aliases
    validate_targets(cases, catalog)
    if args.preflight:
        missing = [case["title"] for case in cases if case["kind"] == "coverage" and not coverage_matches(case, catalog)[0]]
        print(json.dumps({"inputs": len(cases), "by_kind": dict(Counter(case["kind"] for case in cases)),
                          "retrieval_targets": len({target for case in cases if case["kind"] == "retrieval" for target in case["expected_ids"]}),
                          "coverage_missing": missing, "suite_sha256": digest}, ensure_ascii=False, indent=2))
        return
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    checkpoint = output.with_suffix(".jsonl")
    # /api/health may initialize a cold engine, so guard it as well as searches.
    check_system_space(args.min_system_free_gb)
    with httpx.Client(base_url=args.api_url, timeout=180, headers={"X-CineScene-Session": "broad-quality-diagnostics-v1"}) as client:
        response = client.get("/api/health")
        response.raise_for_status()
        start_status = engine_fingerprint(response.json()["engine"])
        header = {"suite_sha256": digest, "engine": start_status}
        rows = []
        if checkpoint.exists():
            if not args.resume:
                raise ValueError("Checkpoint exists; choose a new output or use --resume")
            saved = [json.loads(line) for line in checkpoint.read_text(encoding="utf-8").splitlines() if line]
            if saved[0] != header:
                raise ValueError("Suite or engine differs from this checkpoint")
            rows = saved[1:]
            if [row["id"] for row in rows] != [case["id"] for case in cases[:len(rows)]]:
                raise ValueError("Checkpoint is not a valid case prefix")
        else:
            checkpoint.write_text(json.dumps(header) + "\n", encoding="utf-8")
        with checkpoint.open("a", encoding="utf-8") as handle:
            for case in cases[len(rows):]:
                check_system_space(args.min_system_free_gb)
                row = execute_case(client, case, catalog)
                rows.append(row)
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                handle.flush()
                print(f"[{len(rows)}/{len(cases)}] {case['id']} kind={row['kind']} rank={row['rank']} status={row['status']}", flush=True)
                if len(rows) % 10 == 0:
                    write_report(output, suite, digest, start_status, None, len(cases), rows)
        end = client.get("/api/health")
        end.raise_for_status()
        report = write_report(output, suite, digest, start_status, engine_fingerprint(end.json()["engine"]), len(cases), rows)
        print(json.dumps({key: value for key, value in report.items() if key != "rows"}, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
