"""Enrich existing scene records without decoding a whole movie again."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import fields
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ingestion.media_intelligence import caption_keyframe, release_media_models, resolve_subtitle_files
from ingestion.offline_video import (
    INGESTION_DIR, SceneRecord, _infer_mood_and_keywords, clean_media_title,
    find_sidecar_subtitles, load_subtitle_segments, rebuild_offline_catalog_from_scene_files,
    save_scene_records, subtitle_text_for_range,
)


def enrich_saved_scenes(scene_file: Path, transcribe=False, vision=True):
    rows = json.loads(scene_file.read_text(encoding="utf-8"))
    if not rows:
        raise ValueError("No saved scenes were found.")
    video = Path(rows[0]["source_video"])
    media_id = str(rows[0]["scene_id"]).split("-")[0]
    subtitle_resolution = resolve_subtitle_files(video, find_sidecar_subtitles(video), INGESTION_DIR / "transcripts" / media_id,
                                                 extract_embedded=True, transcribe=transcribe)
    segments = load_subtitle_segments(subtitle_resolution["paths"])
    allowed = {item.name for item in fields(SceneRecord)}
    records = []
    for position, row in enumerate(rows, 1):
        payload = {key: value for key, value in row.items() if key in allowed}
        payload.setdefault("scene_number", position)
        payload["movie_title"] = clean_media_title(payload["movie_title"])
        record = SceneRecord(**payload)
        if segments:
            record.transcript = subtitle_text_for_range(segments, record.start_sec, record.end_sec)
            record.subtitle_sources = [path.name for path in subtitle_resolution["paths"]]
        if vision and "blip" not in record.caption_source and record.keyframe_path:
            caption = caption_keyframe(Path(record.keyframe_path))
            if caption:
                record.visual_caption = caption
                record.caption_source = "blip"
            else:
                record.analysis_warnings.append("Visual captioning did not return a description.")
        inferred = _infer_mood_and_keywords(record.transcript + " " + record.visual_caption)
        record.mood_tags = inferred["mood_tags"]
        record.keywords = inferred["keywords"]
        records.append(record)
        if position % 10 == 0 or position == len(rows):
            print(f"Enriched {position}/{len(rows)} scenes", flush=True)
    save_scene_records(records, records[0].scene_id.split("-")[0])
    release_media_models()
    report = rebuild_offline_catalog_from_scene_files()
    report["enrichment"] = {"scenes": len(records), "vision_scenes": sum("blip" in item.caption_source for item in records),
                            "dialogue_scenes": sum(bool(item.transcript) for item in records)}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scene_file", type=Path)
    parser.add_argument("--transcribe", action="store_true")
    parser.add_argument("--no-vision", action="store_true")
    parser.add_argument("--reindex", action="store_true")
    args = parser.parse_args()
    report = enrich_saved_scenes(args.scene_file, args.transcribe, not args.no_vision)
    if args.reindex:
        from scene_index import build_scene_index
        from multilingual_index import INDEX_PATH, build_multilingual_index

        report["scene_index"] = build_scene_index(batch_size=16)
        if INDEX_PATH.exists():
            report["multilingual"] = build_multilingual_index(scene_only=True, batch_size=16)
    print(json.dumps(report, indent=2, ensure_ascii=True))
