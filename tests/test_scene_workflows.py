from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.storage import AppMemory
from backend.scene_library import read_timeline
from evaluation_metrics import expected_rank, matches, summarize
from ingestion.offline_video import _copy_video, find_sidecar_subtitles
from ingestion.subtitles import load_subtitle_segments, subtitle_text_for_range
from ingestion.media_intelligence import resolve_subtitle_files, transcribe_to_srt


class SubtitleTests(unittest.TestCase):
    def test_persian_encodings_and_boundary(self):
        with tempfile.TemporaryDirectory() as folder:
            for encoding in ("utf-8-sig", "utf-16", "cp1256"):
                path = Path(folder) / "persian.srt"
                content = "1\n00:00:00,000 --> 00:00:02,000\nسلام دنیا\n\n2\n00:00:02,000 --> 00:00:04,000\nکارآگاه\n"
                if encoding == "cp1256":
                    content = content.replace("ی", "ي").replace("ک", "ك")
                path.write_text(content, encoding=encoding)
                segments = load_subtitle_segments(path)
                self.assertEqual(subtitle_text_for_range(segments, 0, 2), "سلام دنیا")
                self.assertEqual(subtitle_text_for_range(segments, 2, 4), "کارآگاه")

    def test_vtt_settings_markup_numeric_dialogue_and_dedup(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "track.vtt"
            path.write_text("WEBVTT\n\ncue-1\n00:00.000 --> 00:02.000 align:start position:0%\n<v Speaker><b>Hello</b> &amp; welcome\n\n00:02.000 --> 00:03.000\n1984\n", encoding="utf-8")
            segments = load_subtitle_segments([path, path])
            self.assertEqual(len(segments), 2)
            self.assertIn("Hello & welcome", segments[0]["text"])
            self.assertEqual(segments[1]["text"], "1984")

    def test_long_dialogue_is_not_truncated(self):
        content = "important dialogue " * 100
        self.assertEqual(subtitle_text_for_range([{"start": 0, "end": 10, "text": content}], 0, 10), content)

    def test_empty_subtitles_allow_speech_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            empty = root / "empty.srt"
            empty.write_text("", encoding="utf-8")
            generated = root / "generated.srt"
            generated.write_text("1\n00:00:00,000 --> 00:00:01,000\nhello\n", encoding="utf-8")
            with patch("ingestion.media_intelligence.transcribe_to_srt", return_value=generated) as transcribe:
                resolved = resolve_subtitle_files(root / "test.mp4", [empty], root, extract_embedded=False, transcribe=True)
                transcribe.assert_called_once()
                self.assertEqual(resolved["paths"], [generated])
                self.assertTrue(resolved["warnings"])

    def test_lazy_speech_errors_have_context(self):
        class BrokenWhisper:
            def transcribe(self, *args, **kwargs):
                def segments():
                    raise RuntimeError("decoder failed")
                    yield
                return segments(), None

        with tempfile.TemporaryDirectory() as folder, patch("ingestion.media_intelligence._whisper_model", return_value=BrokenWhisper()), patch("ingestion.media_intelligence.importlib.util.find_spec", return_value=object()):
            with self.assertRaisesRegex(RuntimeError, "Speech transcription failed.*decoder failed"):
                transcribe_to_srt(Path("clip.mp4"), Path(folder))


class SceneLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.media_id = "abcdef123456"
        rows = [{"scene_number": i + 1, "start_sec": i * 5, "end_sec": (i + 1) * 5,
                 "movie_title": "A movie", "transcript": "كارآگاه تنها" if i == 40 else "",
                 "caption_source": "blip+visual_signals" if i == 40 else "visual_signals"} for i in range(53)]
        (self.root / f"{self.media_id}_scenes.json").write_text(json.dumps(rows), encoding="utf-8")

    def test_pagination_covers_all_scenes(self):
        numbers = []
        for offset in (0, 24, 48):
            data = read_timeline(self.root, self.media_id, offset=offset)
            numbers.extend(scene["scene_number"] for scene in data["scenes"])
        self.assertEqual(numbers, list(range(1, 54)))
        self.assertFalse(data["has_more"])
        self.assertEqual(data["quality"]["dialogue_scenes"], 1)

    def test_persian_search_and_signal_filter(self):
        data = read_timeline(self.root, self.media_id, query="کارآگاه", signal="dialogue")
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["scenes"][0]["scene_number"], 41)
        self.assertEqual(read_timeline(self.root, self.media_id, signal="vision")["total"], 1)

    def test_identifier_cannot_escape_scene_directory(self):
        with self.assertRaises(ValueError):
            read_timeline(self.root, "../../README")

    def test_api_pagination_validation_and_full_timeline(self):
        client = TestClient(app)
        with patch("ingestion.offline_video.INGESTION_DIR", self.root):
            response = client.get(f"/api/media/{self.media_id}/scenes?offset=48&limit=24")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.json()["scenes"]), 5)
            self.assertEqual(client.get(f"/api/media/{self.media_id}/scenes?limit=1000").status_code, 422)
            self.assertEqual(client.get("/api/media/invalid/scenes").status_code, 400)


class RegressionTests(unittest.TestCase):
    def test_search_request_validation(self):
        client = TestClient(app)
        self.assertEqual(client.post("/api/search", json={"query": "   "}).status_code, 422)
        self.assertEqual(client.post("/api/search", json={"query": "a scene", "media_type": "invalid"}).status_code, 422)

    def test_job_survives_memory_recreation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "memory.sqlite"
            first = AppMemory(path)
            first.save_job({"id": "job-1", "status": "running", "updated_at": 12.5, "progress": 42})
            restored = AppMemory(path).recent_jobs()
            self.assertEqual(restored[0]["id"], "job-1")
            self.assertEqual(restored[0]["progress"], 42)

    def test_sequels_and_episodes_are_distinct(self):
        self.assertFalse(matches("Toy Story 3", ["Toy Story"]))
        self.assertTrue(matches("WALL-E", ["WALL·E"]))
        rows = [{"title": "A Show", "season": 1, "episode": 2}, {"title": "A Show", "season": 1, "episode": 1}]
        self.assertEqual(expected_rank(rows, {"expected": ["A Show"], "season": 1, "episode": 1}), 2)
        self.assertEqual(summarize([{"rank": 1}, {"rank": None}])["hit_at_1"], .5)

    def test_same_filename_different_content_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name, content in (("one", b"first video"), ("two", b"second video")):
                (root / name).mkdir()
                (root / name / "episode.mp4").write_bytes(content)
            with patch("ingestion.offline_video.VIDEO_DIR", root / "stored"):
                first = _copy_video(root / "one" / "episode.mp4")
                second = _copy_video(root / "two" / "episode.mp4")
            self.assertNotEqual(first, second)
            self.assertEqual(first.read_bytes(), b"first video")
            self.assertEqual(second.read_bytes(), b"second video")

    def test_subtitle_selection_does_not_mix_episodes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ("Show.S01E01.fa.srt", "Show.S01E01.en.vtt", "Show.S01E010.srt", "Show.S01E02.srt"):
                (root / name).touch()
            selected = find_sidecar_subtitles(root / "Show.S01E01.mp4")
            self.assertEqual({path.name for path in selected}, {"Show.S01E01.fa.srt", "Show.S01E01.en.vtt"})

    def test_failed_crawl_is_not_reported_as_success(self):
        client = TestClient(app)
        with patch("backend.media_worker.crawl_in_worker", return_value={"documents_created": 0, "jobs": [{"error": "corrupt video"}]}):
            response = client.post("/api/crawl/offline", json={"root": "test"})
            self.assertEqual(response.status_code, 500)
            self.assertIn("corrupt video", response.json()["detail"])
        self.assertEqual(client.post("/api/crawl/offline", json={"root": "test", "min_scene_sec": 20, "max_scene_sec": 10}).status_code, 422)


if __name__ == "__main__":
    unittest.main()
