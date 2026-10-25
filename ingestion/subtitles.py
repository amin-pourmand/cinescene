"""Timed-text loading shared by uploads and generated subtitles."""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Union

import pysubs2


def load_subtitle_segments(paths: Optional[Union[Iterable[Path], Path]]) -> List[Dict]:
    if not paths:
        return []
    subtitle_paths = [paths] if isinstance(paths, Path) else list(paths)
    segments = []
    seen = set()
    for path in subtitle_paths:
        path = Path(path)
        if not path.is_file():
            continue
        raw = path.read_bytes()
        encodings = ["utf-8-sig", "cp1256", "cp1252"]
        if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
            encodings.insert(0, "utf-16")
        text = None
        for encoding in encodings:
            try:
                text = raw.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            raise ValueError(f"Cannot decode subtitle: {path.name}")
        try:
            subtitles = pysubs2.SSAFile.from_string(text, format_=path.suffix.lstrip(".").lower())
        except Exception as exc:
            raise ValueError(f"Cannot parse subtitle {path.name}: {exc}") from exc
        for cue in subtitles:
            if cue.is_comment or cue.end <= cue.start:
                continue
            content = html.unescape(re.sub(r"<[^>]+>", "", cue.plaintext))
            content = re.sub(r"\s+", " ", content).strip()
            content = content.replace("ي", "ی").replace("ك", "ک")
            start, end = max(0, cue.start) / 1000, cue.end / 1000
            identity = (start, end, content)
            if not content or identity in seen:
                continue
            seen.add(identity)
            segments.append({"start": start, "end": end, "text": content, "source": str(path)})
    return sorted(segments, key=lambda item: (item["start"], item["end"]))


def subtitle_text_for_range(segments: List[Dict], start_sec: float, end_sec: float, max_chars=None) -> str:
    # Half-open intervals keep cues ending at a cut out of the following scene.
    parts = dict.fromkeys(
        item["text"] for item in segments
        if item["end"] > start_sec and item["start"] < end_sec
    )
    text = " ".join(parts)
    return text[:max_chars] if max_chars is not None else text
