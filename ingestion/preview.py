"""Create browser-compatible, cached scene previews from local source media."""

from __future__ import annotations

import hashlib
import subprocess
import threading
from pathlib import Path

from ingestion.media_intelligence import ffmpeg_path


PREVIEW_LOCK = threading.Lock()


def browser_scene_clip(source: Path, start: float, end: float, output_dir: Path) -> Path:
    executable = ffmpeg_path()
    if not executable:
        raise RuntimeError("FFmpeg is unavailable for scene preview.")
    if end <= start:
        raise ValueError("The scene time range is invalid.")
    stat = source.stat()
    identity = f"{source.resolve()}:{stat.st_size}:{stat.st_mtime_ns}:{start}:{end}:h264-v1"
    target = output_dir / (hashlib.sha256(identity.encode()).hexdigest()[:24] + ".mp4")
    with PREVIEW_LOCK:
        if target.is_file() and target.stat().st_size:
            return target
        output_dir.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".partial.mp4")
        command = [executable, "-hide_banner", "-loglevel", "error", "-y", "-ss", str(start),
                   "-i", str(source), "-t", str(end - start), "-map", "0:v:0", "-map", "0:a:0?",
                   "-vf", "scale='min(1280,iw)':-2", "-c:v", "libx264", "-preset", "veryfast",
                   "-crf", "23", "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags", "+faststart", str(temporary)]
        try:
            result = subprocess.run(command, capture_output=True, timeout=max(120, (end - start) * 3), check=False)
            if result.returncode or not temporary.is_file() or not temporary.stat().st_size:
                message = result.stderr.decode("utf-8", errors="replace")[-600:]
                raise RuntimeError(f"Unable to prepare this scene for playback: {message}")
            temporary.replace(target)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Scene preview encoding timed out.") from exc
        finally:
            temporary.unlink(missing_ok=True)
    return target
