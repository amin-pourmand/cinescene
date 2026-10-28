"""Compare one prepared reranker on frozen local diagnostics, without re-encoding queries."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runtime_environment import configure_runtime
configure_runtime()
from evaluation_metrics import expected_rank, summarize


def rank_distinct_candidates(scores, candidates):
    if len(scores) != len(candidates):
        raise ValueError("Reranker scores and trace candidates are misaligned")
    seen, ordered = set(), []
    for score, candidate in sorted(zip(scores, candidates), key=lambda pair: -float(pair[0])):
        identity = str(candidate.get("id") or candidate["title"])
        if identity not in seen:
            ordered.append(candidate)
            seen.add(identity)
    return ordered


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--evidence-mode", choices=("original", "snippets"), default="original")
    args = parser.parse_args()
    from core.onnx_models import OnnxReranker
    model = OnnxReranker(args.model, max_length=384)
    traces = json.loads(Path(args.trace).read_text(encoding="utf-8"))
    plots = {}
    if args.evidence_mode == "snippets":
        from hybrid_search import HybridSearchEngine
        from core.story_evidence import story_snippet
        documents = json.loads((ROOT / "data/processed/movies_enriched.json").read_text(encoding="utf-8"))
        plots = {str(row["id"]): row.get("wiki_plot") or row.get("cmu_plot") or row.get("plot") for row in documents}
    rows = []
    for trace in traces:
        candidates, pairs = trace.get("candidates", []), trace.get("pairs", [])
        if pairs:
            if len(pairs) != len(candidates):
                raise ValueError("This trace predates passage-aligned candidates; regenerate it before comparison")
            if plots:
                for candidate, pair in zip(candidates, pairs):
                    plot = plots.get(str(candidate["id"])) if candidate.get("kind") not in {"episode", "scene"} else None
                    if plot:
                        snippet = story_snippet(pair["query"], plot, "", HybridSearchEngine._lexical_tokens)
                        if snippet:
                            pair["text"] = pair["text"].split(" Story evidence:")[0] + " Story evidence: " + snippet
            scores = model.predict([[pair["query"], pair["text"]] for pair in pairs], batch_size=4)
            ordered = rank_distinct_candidates(scores, candidates)
            rank = expected_rank(ordered[:10], trace)
        else:
            ordered, rank = candidates, trace["rank"]
        rows.append({"query": trace["query"], "expected": trace["expected"], "rank": rank,
                     "previous_rank": trace["rank"], "top_3": [row["title"] for row in ordered[:3]]})
        print(f"[{len(rows)}/{len(traces)}] {trace['expected'][0]}: {trace['rank']} -> {rank}", flush=True)
    report = {"model": args.model, "evidence_mode": args.evidence_mode, "description": "Development-only ablation; same frozen candidates, selected evidence policy.",
              **summarize(rows), "rows": rows}
    Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "rows"}))


if __name__ == "__main__":
    main()
