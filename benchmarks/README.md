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

- `broad-report.md`: readable ledger of 196 actual HTTP inputs, including every query, expected title, rank and first suggestion.
- `broad-latest.json`: complete structured broad diagnostic, with ten returned identities per successful request and no private media text/paths.
- `broad-scenarios.json`: frozen bilingual topics, scene descriptions, episode acceptance checks, coverage requests and boundary probes.
- `hybrid-quality-latest.json`: the unchanged 27-query development suite on the release engine.
- `scene-identity-latest.json`: 12 targeted identity/contrast queries, including the exact reported Edge of Tomorrow failure, independent paraphrases and Persian queries.
- `episode-latest.json`: three source-informed checks requiring the correct parent series AND season/episode, not just a matching show title.
- `dataset-expansion.json`: episode-source coverage and attribution for the imported snapshot.
- `passage-quality-latest.json`: the failed E5-small full-plot experiment, retained as an ablation rather than shipped as the default.
- `onnx-crossencoder-only.json`: the no-consensus reranker ablation before rank fusion and the final multilingual recall configuration.
- `onnx-consensus.json`: the rank-consensus ablation; not the selected release policy because targeted scene identity regressed.

These suites have different purposes and must not be pooled into a headline accuracy score. The episode examples are informed by source descriptions and are functional acceptance checks, not unseen human-authored evaluation. Dataset expansion does not automatically improve ranking; compare per-query failures as well as aggregate metrics.

## Broad Diagnostic: 196 Inputs

The production `rrf-v7-passage-evidence` engine was tested sequentially through the running HTTP API, with reranking enabled and no retrieval-policy changes during the run. Preflight checked all 160 retrieval cases against exact catalog IDs, including season/episode availability. The cases span 68 title/version identities. Checkpoints and runtime logs were saved on E. The complete engine fingerprint was unchanged at completion; there were no technical errors or non-200 retrieval responses.

| Retrieval group | Inputs | First | Top five |
| --- | ---: | ---: | ---: |
| English | 97 | 70 (72.2%) | 81 (83.5%) |
| Persian | 61 | 2 (3.3%) | 13 (21.3%) |
| Mixed language | 2 | 1 | 1 |
| Manual cases only | 150 | 63 (42.0%) | 85 (56.7%) |
| Source-informed episode identity | 10 | 10 | 10 |

The clean paired comparison uses the same 60 target stories: English 46/60 first, Persian 2/60 first. English movie plots are 36/40 first, English series plots 10/20 first, and English scene-detail questions 6/14 first. One private local title dominates 40/61 Persian first suggestions; its label and ID are pseudonymized in the published report. This concentration is a symptom requiring investigation, not proof that one isolated change will fix the system.

These are strict intended-title labels, not exhaustive relevance annotations. A description can also fit a film adaptation or another related story, especially when the prompt does not specify a medium. Such alternatives were not systematically judged; do not interpret every non-first intended title as an unequivocally irrelevant first suggestion.

Coverage and probes are excluded from these retrieval metrics. Seventeen of the 20 deliberately selected coverage requests are absent; that is not an estimate of the fraction of all cinema missing. The Dune remakes are checked by requested year, and Money Heist resolves through its exact La Casa de Papel alias. Twelve absent targets still produced nonempty suggestions. All four unrelated/noise queries also produced inappropriate movie suggestions. Invalid inputs passed 8/8; ambiguous probes passed 4/4 only for returning distinct multiple candidates, not for judged relevance.

These results supersede any inference of general reliability from a few successful Persian examples. Before claiming dependable scene retrieval, priorities are genuine cross-language query understanding, calibrated no-match behavior, stronger film/series and scene-level discrimination, and broader authorized evidence coverage. If these cases are used for tuning, they become development data; reserve a new evaluation set rather than reporting the same cases as unseen.

```powershell
.\.venv\Scripts\python.exe scripts/broad_retrieval_benchmark.py --preflight
.\.venv\Scripts\python.exe scripts/broad_retrieval_benchmark.py --output E:/CineSceneCache/cinescene/artifacts/broad-next.json
.\.venv\Scripts\python.exe scripts/broad_retrieval_benchmark.py --output E:/CineSceneCache/cinescene/artifacts/broad-next.json --resume
.\.venv\Scripts\python.exe scripts/summarize_broad_benchmark.py
.\.venv\Scripts\python.exe scripts/summarize_broad_benchmark.py --input E:/CineSceneCache/cinescene/artifacts/broad-next.json --public-json benchmarks/broad-latest.json
```

The runner now checks a 2 GB system-drive free-space floor before each new request. Long CPU inference can expand Windows paging on C even with model files on E. This is a native API diagnostic, not a run of every query in the browser WASM engine, and its observed median 5.02 s / p95 6.026 s latency is not a controlled load benchmark.

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
