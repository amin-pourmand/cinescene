"""Read the complete persisted timeline without loading an embedding model."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict


def scene_quality(scenes: list) -> Dict:
    rows = [scene for scene in scenes if isinstance(scene, dict)]
    count = len(rows)
    dialogue = sum(bool(str(scene.get("transcript") or "").strip()) for scene in rows)
    vision = sum("blip" in str(scene.get("caption_source", "")) for scene in rows)
    frames = sum(bool(scene.get("keyframe_path")) for scene in rows)
    return {
        "scenes": count,
        "dialogue_scenes": dialogue,
        "vision_scenes": vision,
        "keyframes": frames,
        "dialogue_coverage": round(dialogue / count, 4) if count else 0,
        "vision_coverage": round(vision / count, 4) if count else 0,
        "duration_sec": max((float(scene.get("end_sec") or 0) for scene in rows), default=0),
        "warnings": sorted({warning for scene in rows for warning in scene.get("analysis_warnings", [])}),
    }


def read_timeline(directory: Path, media_id: str, offset: int = 0, limit: int = 24,
                  query: str = "", signal: str = "all") -> Dict:
    if not re.fullmatch(r"[a-f0-9]{12}", media_id):
        raise ValueError("Invalid media identifier.")
    scene_file = directory / f"{media_id}_scenes.json"
    if not scene_file.is_file():
        raise FileNotFoundError("The media timeline was not found.")
    rows = json.loads(scene_file.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not rows:
        raise FileNotFoundError("No scene records are available for this media.")
    scenes = []
    for position, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            continue
        scene = dict(row)
        scene["scene_number"] = scene.get("scene_number") or position
        scenes.append(scene)
    scenes.sort(key=lambda scene: float(scene.get("start_sec") or 0))
    if not scenes:
        raise FileNotFoundError("No valid scene records are available for this media.")
    first = scenes[0]
    normalize = lambda value: re.sub(r"\s+", " ", str(value).replace("ي", "ی").replace("ك", "ک").replace("\u200c", " ")).casefold().strip()
    terms = normalize(query).split()
    matched = []
    for scene in scenes:
        if signal == "dialogue" and not str(scene.get("transcript") or "").strip():
            continue
        if signal == "vision" and "blip" not in str(scene.get("caption_source", "")):
            continue
        text = normalize(" ".join([
            str(scene.get("transcript") or ""), str(scene.get("visual_caption") or ""),
            " ".join(scene.get("keywords", []) or []), " ".join(scene.get("mood_tags", []) or []),
        ]))
        if all(term in text for term in terms):
            matched.append(scene)
    return {
        "media_id": media_id,
        "title": first.get("movie_title") or first.get("title") or "Untitled media",
        "media_type": first.get("media_type") or "movie",
        "season": first.get("season"), "episode": first.get("episode"),
        "source_video": first.get("source_video", ""),
        "quality": scene_quality(scenes), "total": len(matched),
        "offset": offset, "limit": limit,
        "has_more": offset + limit < len(matched),
        "scenes": matched[offset:offset + limit],
    }
