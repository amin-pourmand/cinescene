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

The earlier CPU-ONNX snapshot (59.26% Hit@1, 77.78% Hit@5, MRR@10 0.6821) is preserved in `hybrid-quality-before-evidence.json`. Current `hybrid-quality-latest.json` measures **74.07% Hit@1**, **92.59% Hit@5**, **MRR@10 0.8111** on the same 27-query hash. Mean observed in-process latency was 6.65 seconds. Previous reports used HTTP and different host load; these timings are not controlled throughput measurements.

## Diverse Scene Evaluation, 2026-10-26

```powershell
.\.venv\Scripts\python.exe scripts/retrieval_quality_benchmark.py --reranker --cases benchmarks/diverse-dev-cases.json --output benchmarks/diverse-dev-latest.json
.\.venv\Scripts\python.exe scripts/retrieval_quality_benchmark.py --reranker --cases benchmarks/diverse-reserved-cases.json --output benchmarks/diverse-reserved-latest.json
```

The 24-query development suite covers remembered scenes, time-loop contrasts, series plots, five Persian descriptions and explicit media/year/director/genre filters. The benchmark now actually forwards case-specific media/scope options. The 16 reserved queries concern disjoint titles; their baseline report was saved without inspecting it during implementation. `quality-policy.json` records the policy frozen before reading final reserved results. No runtime rule maps a test sentence to an expected title.

| Suite | Hit@1 Before / After | Hit@5 Before / After | MRR@10 Before / After |
| --- | ---: | ---: | ---: |
| Diverse development (24) | 58.33% / 79.17% | 70.83% / 95.83% | 0.6414 / 0.8802 |
| Reserved final (16) | 68.75% / 68.75% | 87.50% / 87.50% | 0.7578 / 0.7734 |
| Targeted identity (12) | 75% / 66.67% | 91.67% / 100% | 0.8299 / 0.8125 |

The development gains do not generalize into a higher reserved Hit@1/Hit@5. In particular, the three reserved Persian queries rank 4, absent and 8, while all five development Persian queries rank first. Concept expansion is not a full translator. The scene about Inception's rotating corridor remains difficult: the new scene-only wording ranks 8, while the older richer description ranks 2. Two English Edge of Tomorrow paraphrases regressed to rank 2. Titanic ranks 6 and the original Dark Knight description is absent from ten. These limitations are recorded rather than removed from the suites. All three episode-identity acceptance checks still pass first.

`diverse-dev-mxbai-ablation.json` tests an already prepared alternative reranker over frozen candidates. It raises Hit@1 to 83.33% but lowers Hit@5 and loses a previously successful Persian Edge of Tomorrow query. `diverse-dev-snippets-ablation.json` tests stitched plot sentences; it loses the hallway match. Neither is the release policy. `scripts/compare_reranker.py` reproduces these local trace-based experiments. Traces can contain private upload text, so keep `--trace` outputs on E and do not publish them.

To refresh the same sourced series metadata and its changed title vectors, stop Studio, run `scripts/expand_episode_dataset.py`, then `scripts/refresh_series_index.py`, rebuild the public catalog/index and restart Studio. Existing vectors for unchanged titles are retained. Local model, cache and test artifacts remain on E; do not run model inference and browser WASM inference simultaneously on low-memory Windows hosts.

This suite has informed development and contains synthetic fixtures. It is **not held-out**, is too small for a reliable general accuracy estimate, and must not be presented as an independent academic test. A defensible final study requires unseen descriptions, human relevance judgments, larger authorized scene/episode coverage, per-language metrics, and separately labeled timestamp relevance.

## Functional Evidence

`scripts/runtime_acceptance.py --upload` tests a real multipart video/subtitle upload through the running API, completion, automatic index refresh, film/series filters, full 153-scene pagination, HTTP range playback, and two real-film dialogue queries. Its private report is saved to `artifacts/runtime-acceptance.json`; source paths and full subtitle text are not committed.

The real-film sample has 153 visual captions and 115 scenes containing timed text. Two inspected dialogue fragments retrieved the film and the corresponding starts at 348.22s and 540.08s at rank 1. These are acceptance examples derived from available evidence, not independent test queries. BLIP captions can be inaccurate, and recovered subtitle tracks can contain credits or other non-spoken text.

`reranked.json` is a legacy ten-query report using the old matcher. `multilingual-only.json` records an earlier small-model experiment before the final base-model index and scene enrichment. Neither is the current release score, and the old 90% first-result claim is superseded.
