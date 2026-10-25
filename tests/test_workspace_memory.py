import tempfile
import sqlite3
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend.main import app
from backend.storage import AppMemory


class WorkspaceMemoryTests(unittest.TestCase):
    def test_identically_named_movies_and_episodes_are_saved_separately(self):
        with tempfile.TemporaryDirectory() as folder:
            memory = AppMemory(Path(folder) / "test.sqlite")
            for movie_id in ("episode:1", "episode:2"):
                memory.add_favorite("first", {"id": movie_id, "title": "A show"})
            self.assertEqual(len(memory.favorites("first")), 2)

    def test_legacy_saved_items_survive_key_migration(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "legacy.sqlite"
            with sqlite3.connect(path) as conn:
                conn.execute("""CREATE TABLE favorites (id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL, movie_id TEXT, title TEXT NOT NULL, payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(session_id, title))""")
                conn.execute("INSERT INTO favorites(session_id,movie_id,title,payload_json,created_at) VALUES(?,?,?,?,?)",
                             ("first", "episode:1", "A show", json.dumps({"id": "episode:1", "title": "A show"}), "2026-10-24 10:00:00"))
            conn.close()
            memory = AppMemory(path)
            memory.add_favorite("first", {"id": "episode:2", "title": "A show"})
            saved = memory.favorites("first")
            self.assertEqual(len(saved), 2)
            self.assertEqual(next(item for item in saved if item["id"] == "episode:1")["favorited_at"], "2026-10-24 10:00:00")

    def test_removing_a_favorite_is_idempotent_and_session_scoped(self):
        with tempfile.TemporaryDirectory() as folder:
            memory = AppMemory(Path(folder) / "test.sqlite")
            movie = {"id": "movie:1", "title": "A movie"}
            for session in ("first", "second"):
                memory.add_favorite(session, movie)
            memory.remove_favorite("first", movie)
            memory.remove_favorite("first", movie)
            self.assertEqual(memory.favorites("first"), [])
            self.assertEqual(memory.favorites("second")[0]["id"], "movie:1")

    def test_api_clear_history_does_not_remove_other_sessions_or_favorites(self):
        with tempfile.TemporaryDirectory() as folder:
            memory = AppMemory(Path(folder) / "test.sqlite")
            movie = {"id": "movie:1", "title": "A movie"}
            for session in ("first", "second"):
                memory.add_search(session, "scene", 5, False, [movie])
                memory.add_favorite(session, movie)
            client = TestClient(app)
            with patch("backend.main.memory", memory):
                headers = {"X-CineScene-Session": "first"}
                self.assertEqual(client.delete("/api/history", headers=headers).status_code, 200)
                self.assertEqual(client.get("/api/history", headers=headers).json()["items"], [])
                self.assertEqual(len(memory.recent_searches("second")), 1)
                self.assertEqual(len(memory.favorites("first")), 1)
                response = client.request("DELETE", "/api/favorites", headers=headers, json={"movie": movie})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(memory.favorites("first"), [])
                self.assertEqual(len(memory.favorites("second")), 1)
