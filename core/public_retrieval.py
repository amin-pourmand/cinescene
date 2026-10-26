"""Public story passages; local media is admitted only by the catalog allowlist."""

from __future__ import annotations

import re


def relevance_text(item, evidence=""):
    title = str(item.get("title") or "Untitled")
    overview = str(item.get("overview") or "").strip()
    pieces = [f"Title: {title}.", "Genres: " + ", ".join(item.get("genres", [])) + ".",
              "Keywords: " + ", ".join(item.get("keywords", [])[:18]) + "."]
    summary_passage = f"{title} ({item.get('year', '')}). " + overview
    if evidence and evidence != summary_passage:
        pieces.append("Evidence: " + evidence)
    if overview:
        pieces.append("Plot: " + overview)
    return " ".join(pieces)


def fuse_verification(candidates, verification_scores):
    verified_order = sorted(range(len(candidates)), key=lambda i: -float(verification_scores[i]))
    verified_ranks = {index: rank for rank, index in enumerate(verified_order, 1)}
    return sorted([{**candidate, "score": 1 / (61 + i) + 1 / (60 + verified_ranks[i]), "method": "rank-fusion"}
                   for i, candidate in enumerate(candidates)], key=lambda row: -row["score"])


def passages_for(item):
    title = str(item.get("title") or "Untitled")
    context = f"{title} ({item.get('year', '')}). "
    overview = str(item.get("overview") or "").strip()
    if overview:
        yield {"text": context + overview, "kind": "story", "scene": None}
    plot = str(item.get("plot") or "").strip()
    if not plot:
        plot = " ".join(str(scene) for scene in item.get("scenes", []) if isinstance(scene, str))
    # Sentence-aware windows keep the action, cause and consequence together.
    sentences = re.split(r"(?<=[.!?])\s+", plot)
    windows, window, count = [], [], 0
    for sentence in sentences:
        words = sentence.split()
        if count + len(words) > 160 and window:
            windows.append(" ".join(window))
            window, count = window[-1:], len(window[-1].split())
        window.append(sentence)
        count += len(words)
    if window:
        windows.append(" ".join(window))
    seen = {overview.casefold()}
    for text in windows:
        if text.casefold() not in seen and text:
            seen.add(text.casefold())
            yield {"text": context + text, "kind": "story", "scene": None}
    for i, scene in enumerate(item.get("scene_timeline", [])):
        text = " ".join(str(scene.get(key) or "") for key in ("transcript", "visual_caption")).strip()
        if text:
            yield {"text": context + text, "kind": "scene", "scene": i}
    if not overview and not plot and not item.get("scene_timeline"):
        yield {"text": context, "kind": "title", "scene": None}


def catalog_passages(items):
    records = []
    for index, item in enumerate(items):
        records.extend({"item": index, **passage} for passage in passages_for(item))
    return records
