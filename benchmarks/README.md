# Retrieval Evaluation

## Public Runtime Verification

The `PWA Semantic Acceptance` workflow runs `scripts/pwa_semantic_acceptance.mjs` against the exact exported public catalog/index, using the same `docs/assets/search-runtime.mjs` as the browser worker. It records all 26 paired English/Persian retrieval inputs from `recent-movie-scenarios.json`, their ranks, interpreted sentences, top results and errors. This is an inspected development cohort, not a held-out accuracy claim. GitHub's CPU runtime is not a WASM latency measurement, and policy/data alignment does not guarantee numerically identical native/browser rankings.

The [completed real-model run](https://github.com/amin-pourmand/cinescene/actions/runs/40694924629) is preserved in [`pwa-semantic-v12.json`](pwa-semantic-v12.json): **16/26 Hit@1 (61.54%), 22/26 Hit@5 (84.62%), no technical errors and no reduced-capability translations**. Dune: Part Two and Project Hail Mary still miss the Persian Top-10; their English versions rank sixth and second. Poor Things ranks eighth in English and third in Persian. The exact reported Edge of Tomorrow query ranks second in English and first in Persian. Passing workflow execution does not mean every retrieval is correct; these failures are part of the release evidence. No no-match probes ran in this JS cohort.

The subsequent [native comparison ledger](recent-movies-native-v12.md) retains all 28 requests: 15/26 first, 21/26 Top-5, one HTTP 500 from history persistence, and zero of two unrelated probes correctly rejected. Among the 25 retrieval requests that returned native results, **23 intended-title ranks match the public JS run**. Poor Things in Persian ranks 2 versus 3, and Conclave in Persian ranks 2 versus 4. This is intended-title-rank agreement, not equality of complete result lists. Corresponding models/conversions can differ, and both systems retain the same major semantic misses.

The native run exposed `sqlite3.OperationalError: database is locked` after Anora's English ranking completed. The failure remains in the report; it was not regraded as a successful result. Follow-up storage hardening enables WAL/bounded waits and returns completed results with an explicit unsaved-history warning on SQLite write errors. Two regression tests cover a real open reader and the API failure path. Changing database journal mode during this diagnostic means its availability/timing is not a frozen storage-performance benchmark; its retrieval model/index fingerprint stayed unchanged.

[`recent-movies-v11.md`](recent-movies-v11.md) retains the complete preceding native run: 16/26 first (61.54%), 20/26 Top-5 (76.92%), one translation error, and neither unrelated probe correctly rejected. It precedes the narrative-first document rebuild. A later local 28-input attempt encountered 17 resource-guard errors while the host was busy; it is not a completed new ranking-quality estimate. Do not silently exclude availability failures or relabel historical metrics as the new public release.

## Native v9 Language And Evidence Check

[`broad-v9.md`](broad-v9.md) and [`broad-v9.json`](broad-v9.json) preserve the complete 196-input rerun on the original 8,163 title/episode records plus 158 scenes. The ranking policy stayed unchanged during evaluation. Overall intended-title Hit@1 was 107/160 (66.9%), Hit@5 130/160 (81.2%). Persian improved from 2/61 first to 35/61 first (57.4%); English remained 70/97 first (72.2%), with Top-5 increasing from 81 to 82. This is a development diagnostic comparison, not independent population accuracy or evidence of fine-tuning.

The same 60 paired stories returned English first 47/60 and Persian first 34/60. Four unrelated inputs still received movie suggestions; calibrated no-match behavior remains unresolved. Scene-detail intended-title accuracy is 7/14, so this release must not be described as universal scene recognition. These measurements precede the separate 50-show expansion and cannot be relabeled as its results.

[`bilingual-transfer-v8.md`](bilingual-transfer-v8.md) preserves an earlier 32-input transfer diagnostic across 16 different target titles: 25/32 first, 29/32 Top-5. English and Persian had 16 inputs each. The run spans a memory-configuration change and uses the preceding v8 passage policy; its latency is not a clean performance benchmark. It is not interchangeable with the v9 report. None of these questions trained model weights.

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

## Historical Broad v7 Diagnostic

The earlier `rrf-v7-passage-evidence` engine was tested sequentially through the running HTTP API, with reranking enabled and no retrieval-policy changes during the run. [`broad-v7.md`](broad-v7.md) and [`broad-v7.json`](broad-v7.json) preserve this baseline. Preflight checked all 160 retrieval cases against exact catalog IDs, including season/episode availability. The cases span 68 title/version identities. Checkpoints and runtime logs were saved on E. The complete engine fingerprint was unchanged at completion; there were no technical errors or non-200 retrieval responses.

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

The runner now checks a 2 GB system-drive free-space floor before the initial health request (which can initialize a cold engine) and each search. This guard does not cap Windows memory or pagefile allocation; long CPU inference can still expand paging on C even with model files on E. This is a native API diagnostic, not a run of every query in the browser WASM engine, and its observed median 5.02 s / p95 6.026 s latency is not a controlled load benchmark.

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

## Recent Film Coverage

`dataset-expansion-v11.json` records the installed film expansion: 4,979 catalog films, 176 newly added catalog titles, 230 attributed film records and 229 full plot sections. The complete native index contains 7,819 parent titles, 3,416 episode summaries and 158 actual video scenes. Source selections include annual top-ten lists through 2026 and an explicit international/genre cohort. These are coverage counts, not a model accuracy result or a claim to include every famous movie.

`recent-movie-scenarios.json` has 13 manual English/Persian target pairs and two unrelated-input probes. Exact sequel/version identities are checked. Related adaptations can still make a natural-language query ambiguous; do not revise labels or omit failed rows to improve a score. Run against the already started native Studio, with all artifacts on the data drive:

```powershell
.\.venv\Scripts\python.exe scripts/broad_retrieval_benchmark.py --cases benchmarks/recent-movie-scenarios.json --preflight
.\.venv\Scripts\python.exe scripts/broad_retrieval_benchmark.py --cases benchmarks/recent-movie-scenarios.json --output E:/CineSceneCache/cinescene/artifacts/recent-movies-next.json
```

Cold-start availability and retrieval correctness are separate. A preliminary nine-input run during the storage migration encountered one 503 at the old 90-second translation deadline; its checkpoint is retained locally and is not a completed accuracy report. The bounded deadline is now configurable, without increasing worker memory caps. Avoid simultaneous large storage migrations and model benchmarks when measuring latency.

## Functional Evidence

`scripts/runtime_acceptance.py --upload` tests a real multipart synthetic video/subtitle upload through the running API, completion, automatic index refresh and film/series filters. Optional `--real-media-id` and repeatable `--real-dialogue-query` arguments enable private full-timeline pagination, HTTP range playback and real-film dialogue checks. There are no private film IDs or subtitle quotes in the default test source. Private reports are saved under `artifacts/`; source paths and full subtitle text are not committed.

The real-film sample has 153 visual captions and 115 scenes containing timed text. Two inspected dialogue fragments retrieved the film and the corresponding starts at 348.22s and 540.08s at rank 1. These are acceptance examples derived from available evidence, not independent test queries. BLIP captions can be inaccurate, and recovered subtitle tracks can contain credits or other non-spoken text.

`reranked.json` is a legacy ten-query report using the old matcher. `multilingual-only.json` records an earlier small-model experiment before the final base-model index and scene enrichment. Neither is the current release score, and the old 90% first-result claim is superseded.
