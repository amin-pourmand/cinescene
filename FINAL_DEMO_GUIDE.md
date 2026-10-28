# CineScene Final Demo Guide

This walkthrough demonstrates the complete user story in a short, defensible order: **upload a video, turn it into scene memory, then retrieve its title from a remembered scene.**

## 1. Public First Impression

Open:

```text
https://amin-pourmand.github.io/cinescene
```

Show the installable PWA, browser memory, matched story/episode evidence and synthetic scene timelines. Search performs real on-device hybrid inference; the first query downloads pinned models with visible progress and cancellation. It is not the original keyword-only demo. Video ingestion still needs local Studio.

## 2. Start The Full Runtime

```powershell
Set-Location E:\CineScene
.\.venv\Scripts\python.exe app.py
```

Open `http://127.0.0.1:8000` and hard-refresh once with `Ctrl+F5` if an older cached stylesheet is visible.

The sidebar status should become **Engine online**. Under **Settings > Runtime diagnostics**, the metrics should report:

- catalog-title, episode-vector and scene-vector counts from the current runtime, not a hard-coded total;
- 3 currently ingested offline media documents;
- CPU int8 ONNX for search, with sequential encoder loading. Optional vision/transcription can use CUDA separately.

Expand the runtime diagnostics and briefly show that scene detection, FFmpeg subtitles, faster-whisper, BLIP vision, the movie index, and the scene index are independently observable. They are intentionally kept off the main Search screen.

The installed October 28 film generation has 4,979 catalog films, 7,819 parent titles, 3,416 episode summaries and 158 video scene records. It adds 176 films and refreshes 230 source-verified films, with full plot prose for 229 of them. The explicit source selection includes recent releases through 2026; it is not exhaustive coverage of every famous film. Inspect the pinned Wikipedia revision links in story details. Plot prose does not provide a video timestamp.

## 3. Prove Scene Retrieval

Run these searches in **Search**:

```text
a lonely detective enters a dark room and investigates a mystery
```

```text
کارآگاهی تنها وارد اتاقی تاریک می شود و دنبال سرنخ می گردد
```

Open **Details** to inspect the matched keyframe, transcript, timestamp and source label. Raw ranking scores are not confidence percentages. Save the title, open it from **Saved & history**, then demonstrate removal. Copy the search link to reproduce the query and filter. Report the actual result rather than assuming every Persian query ranks first.

For a real local-film example, choose an authorized video from **Your videos**, open its recovered dialogue, and search a distinctive fragment. Verify the returned title, frame and timecode against the timeline. Keep private film names, dialogue and source paths out of screenshots/reports intended for public distribution. Source-informed examples demonstrate the pipeline, not held-out recognition accuracy.

Then try catalog-oriented queries:

```text
an officer that could raise to the life each time after he dies so he can fix the issues and keep soldiers alive and win the battle
```

```text
a shark terrorizes a seaside town
```

## 4. Upload A Video In The App

Open **Your videos > Add a video**, or use **Add video** in the top bar.

1. Drag an MP4/MKV/MOV/AVI/WEBM file into **Media source**.
2. Add SRT/VTT/ASS/SSA tracks when available.
3. Enter a clean movie or episode title.
4. Expand **Processing settings** and keep **Embedded subtitles** enabled.
5. Enable **Speech transcription** only when subtitles are unavailable.
6. Enable **Visual captioning** for the strongest scene descriptions.
7. Choose **Process video**.

The live pipeline should advance through:

```text
Upload
  -> Scene boundaries
  -> Scene intelligence
  -> Vector index
  -> Search ready
```

When complete, choose **Explore scenes** to paginate the full timeline, search recovered text, filter dialogue/vision, and play a selected scene. Inspect the actual dialogue/vision counts rather than assuming full coverage. Return to Search and search for evidence from one scene. No manual full-index rebuild is needed after upload. Progress survives a page refresh; use **Reconnect to processing** if polling loses its connection. A server restart requires retrying interrupted work. Search is temporarily unavailable while video/index models are processing; memory preflight can refuse heavy analysis on a busy host.

## 5. Demonstrate Subtitle Fallbacks

Explain the timed-text priority:

1. attached SRT/VTT/ASS/SSA files;
2. embedded subtitle stream extracted by FFmpeg;
3. faster-whisper transcription when no subtitle is available.

The scene record stores `subtitle_sources` and `caption_source`, so the origin of each generated description is auditable.

## 6. Demonstrate The Folder Crawler

Open **Your videos > Import a folder**. Use **Check folder** to confirm supported videos and sidecar subtitles. This form has independent **Processing settings** for subtitles, speech, vision, and scene detection. Select **Import videos** to start.

Recommended series layout:

```text
D:\Series\Show.Name.S01E01.mkv
D:\Series\Show.Name.S01E01.fa.srt
D:\Series\Show.Name.S01E02.mkv
D:\Series\Show.Name.S01E02.fa.srt
```

CLI equivalent:

```powershell
.\.venv\Scripts\python.exe .\scripts\crawl_offline_videos.py "D:\Series" --min-scene-sec 4 --max-scene-sec 45 --threshold 0.35 --sample-fps 2
```

The crawler recursively detects episodes, parses season/episode metadata, cleans release tags from filenames, and persists one JSON record per scene.

## 7. Run Verification

Fast API and ingestion smoke test:

```powershell
.\.venv\Scripts\python.exe .\scripts\smoke_test_final.py
```

Retrieval quality benchmark:

```powershell
.\.venv\Scripts\python.exe .\scripts\retrieval_quality_benchmark.py
```

Responsive visual regression test:

```powershell
node .\scripts\visual_smoke_test.js http://127.0.0.1:8000
```

The quality report includes Hit@1, Hit@5, MRR@10, latency, and the rank of every expected title. The visual test covers 1440px desktop and 390px mobile, browser errors, and horizontal overflow.

Historical GPU baseline (not current ONNX/browser performance):

```text
Hit@1       0.4815
Hit@5       0.8519
MRR@10      0.5975
Mean query  0.234 s
```

The latest upload regression completed in about 49 seconds including CUDA index refresh, created three timestamped scenes and keyframes, attached the supplied SRT, and returned the English `Benchmark Show` query at rank 1. Its H.264 preview was verified through an HTTP range response and decoded playback in Chrome. Reproduce with `python scripts/runtime_acceptance.py --upload` while the backend runs.

`benchmarks/hybrid-quality-latest.json` and `benchmarks/scene-identity-latest.json` retain historical development results, including the original Edge of Tomorrow failure and paraphrases. They do not establish the accuracy of a newer index generation. The current film expansion's manual bilingual cohort is `benchmarks/recent-movie-scenarios.json`; its source-coverage ledger is `benchmarks/dataset-expansion-v11.json`. Keep failed queries and technical errors in any new report. Neither this small diagnostic cohort nor the historical development sets is an independent population accuracy estimate. The old ten-query 90% claim used permissive substring matching and is superseded.

## 8. Explain The Engineering Decisions

- **Why separate retrieval channels?** Whole-title vectors provide broad plot recall, scene vectors preserve local evidence/timecodes, and multilingual passage vectors extend cross-language and long-plot recall.
- **Why collapse by title?** Multiple matching scenes from one movie should improve that movie's evidence, not flood the result list.
- **Why subtitles plus vision?** Dialogue alone misses silent visual moments; vision alone misses names and exact lines.
- **Why a static PWA and local backend?** GitHub Pages is ideal for a shareable installable showcase but cannot execute Python, FAISS, FFmpeg, or CUDA.
- **Why no Netflix crawler?** Protected streaming automation and DRM bypass are neither legal nor technically appropriate. CineScene accepts authorized local files or a future licensed provider feed.

## 9. Current Scope

CineScene is a working research prototype, not a universal scene-recognition service. Most catalog titles have no ingested scene timeline yet, and the active models are pretrained. Adding authorized films/episodes and reliable subtitles is necessary to broaden actual scene coverage. Current local media, models, indexes, caches, and temporary uploads are stored on E rather than C. Public exports include only allowlisted synthetic fixtures; private film transcripts are not published.
