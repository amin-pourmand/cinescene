"""Exercise the real HTTP upload, indexing, scene library, and playback pipeline."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--upload", action="store_true", help="Reprocess the included six-second synthetic episode.")
    args = parser.parse_args()
    client = httpx.Client(base_url=args.url, timeout=180, headers={"X-CineScene-Session": "runtime-acceptance-v2"})

    def get(path, **kwargs):
        response = client.get(path, **kwargs)
        response.raise_for_status()
        return response.json()

    def search(query, **options):
        response = client.post("/api/search", json={"query": query, "top_k": 5, **options})
        response.raise_for_status()
        return response.json()["results"]

    report = {"transport": "http", "synthetic_fixture": "Benchmark Show S01E01", "checks": {}}
    health = get("/api/health")
    require(health.get("ok"), f"Search engine unavailable: {health.get('error')}")
    if args.upload:
        source = ROOT / "data/offline_videos/benchmark_folder/Benchmark.Show.S01E01.mp4"
        started = time.monotonic()
        with source.open("rb") as video, source.with_suffix(".srt").open("rb") as subtitle:
            response = client.post("/api/ingest/video", data={
                "movie_title": "Benchmark Show", "min_scene_sec": "1", "max_scene_sec": "10",
                "threshold": "0.25", "sample_fps": "2", "extract_embedded_subtitles": "true",
                "enable_vision": "false", "transcribe_audio": "false",
            }, files=[("video", (source.name, video, "video/mp4")),
                      ("subtitles", (source.with_suffix(".srt").name, subtitle, "application/x-subrip"))])
        response.raise_for_status()
        job_id = response.json()["job"]["id"]
        stages = []
        while time.monotonic() - started < 600:
            job = get(f"/api/jobs/{job_id}")
            stage = job.get("stage")
            if not stages or stages[-1] != stage:
                stages.append(stage)
                print(f"Upload pipeline: {stage} ({job.get('progress', 0)}%)", flush=True)
            if job["status"] in {"completed", "failed"}:
                break
            time.sleep(1)
        require(job["status"] == "completed", f"Upload analysis failed or timed out: {job.get('error')}")
        require(job["result"]["report"]["documents_created"] >= 1, "Upload produced no searchable document")
        report["upload"] = {"job_id": job_id, "elapsed_sec": round(time.monotonic() - started, 2),
                            "stages_observed": stages, "result": job["result"]["report"],
                            "scene_index": job["result"]["scene_index"]}

    english = search("suspenseful detective mystery in a dark room")
    require(english and english[0]["title"] == "Benchmark Show", "English fixture was not the top result")
    require(english[0].get("matched_scene", {}).get("transcript"), "Matched scene lost its transcript")
    scene = english[0]["matched_scene"]
    response = client.get(scene["preview_url"], headers={"Range": "bytes=0-1023"})
    require(response.status_code in {200, 206} and len(response.content) > 0, "Browser preview unavailable")
    report["checks"]["synthetic_english_rank"] = 1
    report["checks"]["preview_http_status"] = response.status_code

    persian = search("کارآگاهی تنها وارد اتاقی تاریک می شود و دنبال سرنخ می گردد")
    persian_rank = next((i for i, row in enumerate(persian, 1) if row["title"] == "Benchmark Show"), None)
    require(persian_rank is not None, "Persian synthetic fixture was absent from the top five")
    report["checks"]["synthetic_persian_rank"] = persian_rank

    for kind in ("movie", "series"):
        results = search("detective mystery", media_type=kind)
        require(results and all(row["media_type"] == kind for row in results), f"{kind} filter leaked other media")
    report["checks"]["media_filters"] = True

    media_id = "0a034829e524"
    first = get(f"/api/media/{media_id}/scenes", params={"limit": 24})
    rows = list(first["scenes"])
    for offset in range(24, first["total"], 24):
        rows.extend(get(f"/api/media/{media_id}/scenes", params={"limit": 24, "offset": offset})["scenes"])
    require(len(rows) == first["total"] == 153, "Full real-film timeline is incomplete")
    require(len({row["scene_number"] for row in rows}) == len(rows), "Pagination duplicated scenes")
    report["real_film_quality"] = first["quality"]
    report["real_film_queries"] = []
    for query in ("پاتریشیا پسرها کجان صدای گریه", "در رو ببند لطفاً اون بهمون صدمه میزنه"):
        results = search(query)
        rank = next((i for i, row in enumerate(results, 1) if row["id"] == f"offline:{media_id}"), None)
        require(rank is not None, "Real-film subtitle evidence was absent from the top five")
        match = results[rank - 1]
        report["real_film_queries"].append({"query": query, "rank": rank,
                                            "matched_scenes": [{key: value for key, value in item.items()
                                                                if key in {"scene_number", "start_sec", "end_sec"}}
                                                               for item in match.get("matched_scenes", [])]})
    report["ok"] = True
    path = ROOT / "artifacts/runtime-acceptance.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
