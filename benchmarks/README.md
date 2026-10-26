# Retrieval Evaluation

## Reproduce

```powershell
.\.venv\Scripts\python.exe scripts/retrieval_quality_benchmark.py --api-url http://127.0.0.1:8000
.\.venv\Scripts\python.exe scripts/retrieval_quality_benchmark.py --api-url http://127.0.0.1:8000 --reranker --output benchmarks/reranked-v2.json
```

Omit `--api-url` for in-process evaluation. `--mode semantic|lexical|multilingual|hybrid` supports channel experiments in-process. Each run records the suite SHA-256, models/configuration, exact expected rank, misses, top-three titles, category metrics, and latency. HTTP latency includes serialization and local transport, but excludes initial model loading after warm-up.

## Corrected Development Suite

`cases.json` contains 27 manually authored queries: 12 movie plots, eight series plots, four Persian plots, two English synthetic scenes, and one Persian synthetic scene. Version 2 uses exact normalized titles or explicit aliases/IDs. Sequels are distinct; season/episode identity is checked when specified. Misses contribute zero to Hit@k and MRR@10.

Results on 2026-10-24, using the same suite hash:

| Configuration | Hit@1 | Hit@5 | MRR@10 |
| --- | ---: | ---: | ---: |
| Original engine, corrected matcher (`baseline-v2.json`) | 44.44% | 55.56% | 0.4892 |
| Current hybrid (`latest.json`) | 48.15% | 85.19% | 0.5975 |
| Current hybrid + optional English reranker (`reranked-v2.json`) | 48.15% | 85.19% | 0.6329 |

The baseline was captured on 2026-10-19 before the new multilingual channel and local-film enrichment. This measures the combined system change, not an isolated model ablation. Current retrieval uses BGE-large (1,024 dimensions), multilingual E5-base (768 dimensions), and BM25. There are 7,615 core title vectors, 158 scene vectors, and 22,791 multilingual passage/scene vectors. All active encoders are pretrained, not demonstrated fine-tuned checkpoints.

That historical GPU hybrid run averaged 0.234 seconds per warm HTTP query. The current CPU-ONNX release enables reranking by default and trades latency for first-result relevance. Current results are in `hybrid-quality-latest.json`, not the historical table. First-result accuracy, especially on general Persian descriptions and series, is still limited. Most titles have only plot metadata; only three local titles have complete timelines.

## Current Release Checks

- `hybrid-quality-latest.json`: the unchanged 27-query development suite on the release engine.
- `scene-identity-latest.json`: 12 targeted identity/contrast queries, including the exact reported Edge of Tomorrow failure, independent paraphrases and Persian queries.
- `episode-latest.json`: three source-informed checks requiring the correct parent series AND season/episode, not just a matching show title.
- `dataset-expansion.json`: episode-source coverage and attribution for the imported snapshot.
- `passage-quality-latest.json`: the failed E5-small full-plot experiment, retained as an ablation rather than shipped as the default.
- `onnx-crossencoder-only.json`: the no-consensus reranker ablation before rank fusion and the final multilingual recall configuration.
- `onnx-consensus.json`: the rank-consensus ablation; not the selected release policy because targeted scene identity regressed.

These suites have different purposes and must not be pooled into a headline accuracy score. The episode examples are informed by source descriptions and are functional acceptance checks, not unseen human-authored evaluation. Dataset expansion does not automatically improve ranking; compare per-query failures as well as aggregate metrics.

On the current 27-query CPU-ONNX snapshot: Hit@1 **59.26%**, Hit@5 **77.78%**, MRR@10 **0.6821**, observed mean HTTP latency **4.33 s**. Relative to the historical GPU snapshot, first-result rank improves but top-five coverage is lower. The runtime, quantization, fusion and dataset all changed, so this is a system comparison, not evidence that one isolated model choice caused the difference. Timing on the development host is not a controlled throughput benchmark.

This suite has informed development and contains synthetic fixtures. It is **not held-out**, is too small for a reliable general accuracy estimate, and must not be presented as an independent academic test. A defensible final study requires unseen descriptions, human relevance judgments, larger authorized scene/episode coverage, per-language metrics, and separately labeled timestamp relevance.

## Functional Evidence

`scripts/runtime_acceptance.py --upload` tests a real multipart video/subtitle upload through the running API, completion, automatic index refresh, film/series filters, full 153-scene pagination, HTTP range playback, and two real-film dialogue queries. Its private report is saved to `artifacts/runtime-acceptance.json`; source paths and full subtitle text are not committed.

The real-film sample has 153 visual captions and 115 scenes containing timed text. Two inspected dialogue fragments retrieved the film and the corresponding starts at 348.22s and 540.08s at rank 1. These are acceptance examples derived from available evidence, not independent test queries. BLIP captions can be inaccurate, and recovered subtitle tracks can contain credits or other non-spoken text.

`reranked.json` is a legacy ten-query report using the old matcher. `multilingual-only.json` records an earlier small-model experiment before the final base-model index and scene enrichment. Neither is the current release score, and the old 90% first-result claim is superseded.
