# Data Sources And Coverage

Catalog size is not scene coverage. A title summary, an episode synopsis, recovered timed dialogue and a generated visual caption are different evidence types.

## Episode Expansion

Episode summaries and newly imported show metadata are from [TVmaze](https://www.tvmaze.com), obtained through its [documented public API](https://www.tvmaze.com/api). This imported/adapted metadata is distributed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Each episode retains its TVmaze page, season/episode number and source attribution. Formatting changes remove HTML and normalize fields; no dialogue or timestamps are invented. The software license does not relicense this third-party data.

`scripts/expand_episode_dataset.py` caches source responses under `data/raw/tvmaze/`, retries rate-limited requests, verifies unambiguous show names/years, deduplicates by episode ID and excludes summaries with fewer than eight words. The initial expansion included 537 summaries across 18 shows. The 50-show snapshot activated in local Studio on 2026-10-27 contains 3,416 episode summaries. After reconciling three duplicate source identities, the series catalog has 2,837 records. Its explicit selection is versioned in `ingestion/series_sources.json`; it deliberately addresses known coverage gaps, not a random sample of television. The separately rebuilt public PWA includes these 3,416 summaries; `docs/data/release.json` records its generation and public counts.

Friends, House of Cards and Supernatural had both legacy provider IDs and TVmaze IDs for the same actual series. Exact titles plus 6, 12 and 6 matching main-cast names respectively establish their source identity; ambiguous remakes are not merged by title alone. Canonicalization preserves the legacy provider ID, records aliases and source evidence, reparents episode records and removes only duplicate title vectors. All 3,416 episode records remain. [The v10 source snapshot](benchmarks/dataset-expansion-v10.json) records the evidence endpoints and activation counts. Evaluation normalizes verified ID aliases while retaining the original label IDs for audit; intended titles, versions and queries are unchanged.

Coverage remains partial: episodes with unavailable summaries are absent, and specials without regular season/episode numbers are excluded. The CLI defaults to 100 episodes per selected show; the expanded snapshot uses a higher explicit limit so long series are not silently capped at 100. The generated coverage report records the actual imported count per show. Episode summaries must not be advertised as 3,416 decoded videos, complete scripts or exhaustive scene annotations.

The enriched movie corpus and existing public-series CSV are the project's earlier inputs, not newly collected subtitles. Their original provider terms continue to apply. Do not assume all catalog text is covered by the software license or the TVmaze license.

## Wikipedia Film Expansion

`scripts/expand_movie_dataset.py` uses the documented [MediaWiki Action API](https://www.mediawiki.org/wiki/API:Parsing_wikitext) and [Wikidata APIs](https://www.wikidata.org/wiki/Wikidata:Data_access). Discovery is reproducible from annual ranked box-office tables and `ingestion/movie_sources.json`, including current-year releases. Each imported plot retains the article title/page ID, revision ID, permanent revision URL, contributor attribution, transformation notice and CC BY-SA-4.0 license. See [Wikipedia reuse requirements](https://en.wikipedia.org/wiki/Wikipedia:Reusing_Wikipedia_content). Structured Wikidata facts are CC0. Original TMDB fields retain their original terms; adding Wikipedia prose does not relicense the entire mixed-source record.

No poster/media files are downloaded. Plot prose and synopsis-only coverage are counted separately; neither is represented as a timed scene, subtitle, or completed video analysis. Full-article extracts are requested individually because TextExtracts silently reduces multi-article whole-text requests to one. Source failures block activation; unresolved identity/date selections remain in the coverage report. Data stays local and is not automatically added to the public GitHub Pages bundle.

For enriched shows, a source-linked TVmaze premiere date takes precedence over the older platform-catalog year in filters and presentation. Episode filters use the authoritative parent's genres and premiere year, including when older episode metadata retains a provider year. Canonical TVmaze/IMDb identities take priority during reconciliation; conflicting identities are rejected, and a provider year alone cannot create another copy of an unambiguous show. The refresh also uses official show summaries and canonical genres rather than provider buckets such as "British TV Shows". Original provider data remains in the raw CSV; the refresh function preserves provider genres and, for future refreshes, the pre-refresh year separately. Other historical CSV records can still have platform-specific release years; they have not all been individually reconciled.

## Local Media

Upload only video and subtitle files you are authorized to analyze. Local paths, private transcripts and keyframes are excluded from public export by default. Only the bundled synthetic fixtures are allowlisted. A streaming subscription is not authorization to bypass DRM or republish a film.

Only locally ingested media has measured scene boundaries, recovered dialogue and frame evidence. Episode summaries improve plot/event recall but cannot establish the exact second of a remembered scene.

## Reproducibility

Optional Persian sentence interpretation uses Meta NLLB-200 distilled 600M, with separately pinned CTranslate2 (native) and ONNX (browser) conversions. The browser conversion is [Xenova/nllb-200-distilled-600M](https://huggingface.co/Xenova/nllb-200-distilled-600M), revision `261c31d1a5732c67cdd16d80e8d6088507c7ccea`. Its CC-BY-NC-4.0 license permits this noncommercial research use, not an unrestricted commercial service. Translation is derived model output, not a source subtitle or verified scene fact. No query text is sent to a translation API. Model conversion/runtime differences can change interpretation and final ranks.

The public hybrid manifest pins model revisions and hashes the catalog and vector/posting files. `scripts/validate_public_index.py` rejects mismatched files, broken evidence references and local source paths. Development benchmarks report per-query failures and are not held-out accuracy estimates.
