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
    return parser.parse_args()


def main():
    args = parse_args()
    case_file = Path(args.cases)
    suite = json.loads(case_file.read_text(encoding="utf-8"))
    cases = suite["cases"]
    if args.api_url:
        if args.mode != "hybrid":
            raise ValueError("API evaluation currently supports hybrid mode only.")
        import httpx

        client = httpx.Client(base_url=args.api_url, timeout=180, headers={"X-CineScene-Session": "quality-benchmark-v2"})
        health = client.get("/api/health")
        health.raise_for_status()
        status = health.json()["engine"]

        def retrieve(query, count):
            response = client.post("/api/search", json={"query": query, "top_k": count, "use_reranking": args.reranker})
            response.raise_for_status()
            return response.json()["results"]
    else:
        if args.engine == "passages":
            from core.passage_search import PassageSearchEngine
            engine = PassageSearchEngine(enable_reranker=args.reranker)
        else:
            from hybrid_search import HybridSearchEngine
            engine = HybridSearchEngine(enable_reranker=args.reranker)
        status = engine.status()

        def retrieve(query, count):
            return engine.search(query, top_k=count, use_reranking=args.reranker, mode=args.mode)

    retrieve("movie scene", 1)
    rows = []
    latencies = []
    for case in cases:
        started = time.perf_counter()
        results = retrieve(case["query"], 10)
        latency = time.perf_counter() - started
        latencies.append(latency)
        rank = expected_rank(results, case)
        rows.append(
            {
                "query": case["query"],
                "expected": case["expected"],
                "category": case.get("category", "unclassified"),
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
    print(json.dumps(report, indent=2, ensure_ascii=True))
    print(f"Saved benchmark report to {output}")


if __name__ == "__main__":
    main()
