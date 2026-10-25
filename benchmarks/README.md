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

The default hybrid run averaged 0.234 seconds per warm HTTP query. Reranking increases latency substantially and remains opt-in. First-result accuracy, especially on general Persian descriptions and series, is still limited. Most titles have only plot metadata; only three local titles have complete timelines.

This suite has informed development and contains synthetic fixtures. It is **not held-out**, is too small for a reliable general accuracy estimate, and must not be presented as an independent academic test. A defensible final study requires unseen descriptions, human relevance judgments, larger authorized scene/episode coverage, per-language metrics, and separately labeled timestamp relevance.

## Functional Evidence

`scripts/runtime_acceptance.py --upload` tests a real multipart video/subtitle upload through the running API, completion, automatic index refresh, film/series filters, full 153-scene pagination, HTTP range playback, and two real-film dialogue queries. Its private report is saved to `artifacts/runtime-acceptance.json`; source paths and full subtitle text are not committed.

The real-film sample has 153 visual captions and 115 scenes containing timed text. Two inspected dialogue fragments retrieved the film and the corresponding starts at 348.22s and 540.08s at rank 1. These are acceptance examples derived from available evidence, not independent test queries. BLIP captions can be inaccurate, and recovered subtitle tracks can contain credits or other non-spoken text.

`reranked.json` is a legacy ten-query report using the old matcher. `multilingual-only.json` records an earlier small-model experiment before the final base-model index and scene enrichment. Neither is the current release score, and the old 90% first-result claim is superseded.
