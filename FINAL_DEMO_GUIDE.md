# CineScene Final Demo Guide

This walkthrough demonstrates the complete user story in a short, defensible order: **upload a video, turn it into scene memory, then retrieve its title from a remembered scene.**

## 1. Public First Impression

Open:

```text
https://aminhatesprogramming.github.io/cinescene
```

Show the responsive Retrieval Studio, installable PWA, scene cards, browser memory, and processed scene timeline. Mention that this public build is static by design; the same interface connects to Python, FAISS, and GPU models in the full runtime.

## 2. Start The Full Runtime

```powershell
.\.venv\Scripts\python.exe app.py
```

Open `http://127.0.0.1:8000` and hard-refresh once with `Ctrl+F5` if an older cached stylesheet is visible.

The sidebar status should become **Engine online**. The Discover metrics should report:

- 7,615 catalog/movie vectors;
- 158 scene vectors and 7,773 total vectors;
- 3 currently ingested offline media documents;
- NVIDIA GeForce GTX 1650 Ti through CUDA.

Open **System** and briefly show that scene detection, FFmpeg subtitles, faster-whisper, BLIP vision, the movie index, and the scene index are independently observable.

## 3. Prove Scene Retrieval

Run these searches in **Discover**:

```text
a lonely detective enters a dark room and investigates a mystery
```

```text
کارآگاهی تنها وارد اتاقی تاریک می شود و دنبال سرنخ می گردد
```

For the English synthetic benchmark, `Benchmark Show` should rank first. The Persian fixture is currently within the top five, not reliably first. Point out the matched keyframe, transcript, timestamp, source label, and retrieval score. A scene result provides evidence beyond a whole-film plot; do not treat its score as a confidence percentage.

For a real local-film example, search `پاتریشیا پسرها کجان صدای گریه`. The verified result is *The Curse of La Llorona*, scene 11, starting at 348.22 seconds. `در رو ببند لطفاً اون بهمون صدمه میزنه` matches scene 13 at 540.08 seconds. These are inspected acceptance examples from the ingested subtitle, not held-out research queries.

Then try catalog-oriented queries:

```text
a dream collapses while people run through a rotating hallway
```

```text
a shark terrorizes a seaside town
```

## 4. Upload A Video In The App

Open **Scene Lab**.

1. Drag an MP4/MKV/MOV/AVI/WEBM file into **Media source**.
2. Add SRT/VTT/ASS/SSA tracks when available.
3. Enter a clean movie or episode title.
4. Keep **Embedded subtitles** enabled.
5. Enable **Speech transcription** only when subtitles are unavailable.
6. Enable **Visual captioning** for the strongest scene descriptions.
7. Choose **Analyze and index video**.

The live pipeline should advance through:

```text
Upload
  -> Scene boundaries
  -> Scene intelligence
  -> Vector index
  -> Search ready
```

When complete, choose **Explore all scenes** to paginate the full timeline, search recovered text, filter dialogue/vision, and play a selected scene. The local feature film has 153 scenes, all with visual captions, and 115 with recovered timed text. Return to Discover and search for evidence from one scene. No manual full-index rebuild is needed after upload. Progress survives a page refresh; a server restart requires retrying interrupted work.

## 5. Demonstrate Subtitle Fallbacks

Explain the timed-text priority:

1. attached SRT/VTT/ASS/SSA files;
2. embedded subtitle stream extracted by FFmpeg;
3. faster-whisper transcription when no subtitle is available.

The scene record stores `subtitle_sources` and `caption_source`, so the origin of each generated description is auditable.

## 6. Demonstrate The Folder Crawler

The lower part of Scene Lab supports batch media folders. Use **Probe** before starting to confirm supported videos and sidecar subtitles.

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

Corrected 27-query development regression result:

```text
Hit@1       0.4815
Hit@5       0.8519
MRR@10      0.5975
Mean query  0.234 s
```

The latest upload regression completed in about 49 seconds including CUDA index refresh, created three timestamped scenes and keyframes, attached the supplied SRT, and returned the English `Benchmark Show` query at rank 1. Its H.264 preview was verified through an HTTP range response and decoded playback in Chrome. Reproduce with `python scripts/runtime_acceptance.py --upload` while the backend runs.

The original engine scores 0.5556 Hit@5 under the same corrected suite, compared with 0.8519 now. The old ten-query 90% claim used permissive substring matching and is superseded. These development queries are not held-out, and general Persian/series first-result accuracy still needs work. See `benchmarks/README.md` for limitations and the optional reranker comparison.

## 8. Explain The Engineering Decisions

- **Why separate retrieval channels?** Whole-title vectors provide broad plot recall, scene vectors preserve local evidence/timecodes, and multilingual passage vectors extend cross-language and long-plot recall.
- **Why collapse by title?** Multiple matching scenes from one movie should improve that movie's evidence, not flood the result list.
- **Why subtitles plus vision?** Dialogue alone misses silent visual moments; vision alone misses names and exact lines.
- **Why a static PWA and local backend?** GitHub Pages is ideal for a shareable installable showcase but cannot execute Python, FAISS, FFmpeg, or CUDA.
- **Why no Netflix crawler?** Protected streaming automation and DRM bypass are neither legal nor technically appropriate. CineScene accepts authorized local files or a future licensed provider feed.

## 9. Current Scope

CineScene is a working research prototype, not a universal scene-recognition service. Most catalog titles have no ingested scene timeline yet, and the active models are pretrained. Adding authorized films/episodes and reliable subtitles is necessary to broaden actual scene coverage. Current local media, models, indexes, caches, and temporary uploads are stored on E rather than C. Public exports include only allowlisted synthetic fixtures; private film transcripts are not published.
