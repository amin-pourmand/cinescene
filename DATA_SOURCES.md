# Data Sources And Coverage

Catalog size is not scene coverage. A title summary, an episode synopsis, recovered timed dialogue and a generated visual caption are different evidence types.

## Episode Expansion

Episode summaries and newly imported show metadata are from [TVmaze](https://www.tvmaze.com), obtained through its [documented public API](https://www.tvmaze.com/api). This imported/adapted metadata is distributed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Each episode retains its TVmaze page, season/episode number and source attribution. Formatting changes remove HTML and normalize fields; no dialogue or timestamps are invented. The software license does not relicense this third-party data.

`scripts/expand_episode_dataset.py` caches source responses under `data/raw/tvmaze/`, retries rate-limited requests, verifies unambiguous show names/years, deduplicates by episode ID and excludes summaries with fewer than eight words. The initial expansion includes 537 summaries across 18 shows and 11 newly added shows. This is partial coverage: episodes with unavailable summaries are absent, and long series are capped at 100 episodes by default. The generated coverage report records the exact snapshot.

The enriched movie corpus and existing public-series CSV are the project's earlier inputs, not newly collected subtitles. Their original provider terms continue to apply. Do not assume all catalog text is covered by the software license or the TVmaze license.

For the 18 enriched shows, a source-linked TVmaze premiere date takes precedence over the older platform-catalog year in filters and presentation. The refresh also uses official show summaries and canonical genres rather than provider buckets such as "British TV Shows". Original provider data remains in the raw CSV; the refresh function preserves provider genres and, for future refreshes, the pre-refresh year separately. Other historical CSV records can still have platform-specific release years; they have not all been individually reconciled.

## Local Media

Upload only video and subtitle files you are authorized to analyze. Local paths, private transcripts and keyframes are excluded from public export by default. Only the bundled synthetic fixtures are allowlisted. A streaming subscription is not authorization to bypass DRM or republish a film.

Only locally ingested media has measured scene boundaries, recovered dialogue and frame evidence. Episode summaries improve plot/event recall but cannot establish the exact second of a remembered scene.

## Reproducibility

The public hybrid manifest pins model revisions and hashes the catalog and vector/posting files. `scripts/validate_public_index.py` rejects mismatched files, broken evidence references and local source paths. Development benchmarks report per-query failures and are not held-out accuracy estimates.
