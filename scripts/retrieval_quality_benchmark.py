from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation_metrics import expected_rank, matches, summarize


def parse_args():
    parser = argparse.ArgumentParser(description="Benchmark CineScene scene-to-title retrieval")
    parser.add_argument("--output", default="benchmarks/latest.json")
    parser.add_argument("--reranker", action="store_true", help="Enable the cross-encoder reranker")
    parser.add_argument("--cases", default="benchmarks/cases.json")
    parser.add_argument("--mode", choices=["hybrid", "semantic", "lexical", "multilingual"], default="hybrid")
    parser.add_argument("--api-url", help="Reuse a running backend instead of loading another copy of the models.")
    parser.add_argument("--engine", choices=("hybrid", "passages", "legacy"), default="hybrid")
    parser.add_argument("--trace", help="Save opt-in candidate/evidence diagnostics on the data drive (may contain private upload text).")
    parser.add_argument("--skip-warmup", action="store_true", help="Skip the generic model warmup for a focused diagnostic, not a controlled latency comparison.")
    return parser.parse_args()


def main():
    args = parse_args()
    case_file = Path(args.cases)
    suite = json.loads(case_file.read_text(encoding="utf-8"))
    cases = suite["cases"]
    traces = []
    current_trace = {}
    if args.trace and args.engine != "hybrid":
        raise ValueError("--trace requires a hybrid engine")
    if args.api_url:
        if args.mode != "hybrid":
            raise ValueError("API evaluation currently supports hybrid mode only.")
        import httpx

        client = httpx.Client(base_url=args.api_url, timeout=300, headers={"X-CineScene-Session": "quality-benchmark-v2"})
        health = client.get("/api/health")
        health.raise_for_status()
        status = health.json()["engine"]

        def retrieve(query, count, case=None):
            options = {key: case[key] for key in ("media_type", "scope") if case and key in case}
            response = client.post("/api/search", json={"query": query, "top_k": count, "use_reranking": args.reranker,
                                                       "include_trace": bool(args.trace), **options})
            response.raise_for_status()
            body = response.json()
            if args.trace:
                current_trace.update(body.get("trace") or {})
            return body["results"]
    else:
        if args.engine == "passages":
            from core.passage_search import PassageSearchEngine
            engine = PassageSearchEngine(enable_reranker=args.reranker)
        else:
            from hybrid_search import HybridSearchEngine
            engine = HybridSearchEngine(enable_reranker=args.reranker)
        status = engine.status()
        if args.trace:
            original = engine.rerank_titles
            def traced_rerank(query, candidates, **kwargs):
                current_trace["candidates"] = [
                    {"id": engine.metadata[i].get("parent_id") or engine.metadata[i].get("id"),
                     "title": engine.metadata[i].get("title"), "score": score,
                     "kind": engine.metadata[i].get("record_type", "title"),
                     "matched_episode": engine.metadata[i].get("matched_episode"),
                     "overview": engine.metadata[i].get("overview"), "evidence": kwargs.get("evidence", {}).get(i)}
                    for i, score, _ in candidates[:40]]
                return original(query, candidates, **kwargs)
            engine.rerank_titles = traced_rerank
            if engine.cross_encoder:
                predict = engine.cross_encoder.predict
                def traced_predict(pairs, **kwargs):
                    scores = predict(pairs, **kwargs)
                    indices = getattr(engine, "rerank_pair_indices", [])
                    if len(indices) != len(pairs):
                        raise ValueError("Trace references do not align with evidence pairs")
                    current_trace["trace_version"] = "evidence-pairs-v2"
                    current_trace["candidates"] = [
                        {"id": engine.metadata[i].get("parent_id") or engine.metadata[i].get("id"),
                         "title": engine.metadata[i].get("title"),
                         "kind": engine.metadata[i].get("record_type", "title"),
                         "matched_episode": engine.metadata[i].get("matched_episode"),
                         "overview": engine.metadata[i].get("overview")}
                        for i in indices]
                    current_trace["pairs"] = [{"query": q, "text": text, "score": float(score)}
                                               for (q, text), score in zip(pairs, scores)]
                    return scores
                engine.cross_encoder.predict = traced_predict

        def retrieve(query, count, case=None):
            options = {key: case[key] for key in ("media_type", "scope") if case and key in case}
            return engine.search(query, top_k=count, use_reranking=args.reranker, mode=args.mode, **options)

    if not args.skip_warmup:
        retrieve("movie scene", 1)
    rows = []
    latencies = []
    for case in cases:
        current_trace = dict(case)
        started = time.perf_counter()
        results = retrieve(case["query"], 10, case)
        latency = time.perf_counter() - started
        latencies.append(latency)
        rank = expected_rank(results, case)
        if args.trace:
            current_trace["rank"] = rank
            traces.append(current_trace)
        print(f"[{len(rows) + 1}/{len(cases)}] rank={rank} expected={case['expected'][0]}", flush=True)
        rows.append(
            {
                "query": case["query"],
                "expected": case["expected"],
                "category": case.get("category", "unclassified"),
                "options": {key: case[key] for key in ("media_type", "scope") if key in case},
                "rank": rank,
                "top_3": [item["title"] for item in results[:3]],
                "latency_sec": round(latency, 3),
            }
        )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": status.get("model"),
        "device": status.get("device"),
        "precision": status.get("precision"),
        "embedding_dimension": int(status["embedding_dimension"]),
        "reranker": args.reranker and status.get("reranker", False),
        "transport": "http" if args.api_url else "in_process",
        "warmup": not args.skip_warmup,
        "multilingual": status.get("multilingual", False),
        "multilingual_model": status.get("multilingual_model"),
        "multilingual_vectors": status.get("multilingual_vectors"),
        "fusion_version": status.get("fusion_version"),
        **summarize(rows),
        "evaluation_version": 2,
        "matching": "exact normalized title or explicit id/alias; sequels are distinct",
        "suite_sha256": hashlib.sha256(case_file.read_bytes()).hexdigest(),
        "suite_description": suite.get("description"),
        "retrieval_mode": args.mode,
        "by_category": {category: summarize([row for row in rows if row["category"] == category])
                        for category in sorted({row["category"] for row in rows})},
        "mean_latency_sec": round(statistics.mean(latencies), 4),
        "movie_vectors": status.get("movie_vectors"),
        "scene_vectors": status.get("scene_vectors"),
        "index_vectors": status.get("index_vectors"),
        "rows": rows,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.trace:
        trace_path = Path(args.trace)
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        trace_path.write_text(json.dumps(traces, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=True))
    print(f"Saved benchmark report to {output}")


if __name__ == "__main__":
    main()
