import json
from pathlib import Path
import pickle
import tempfile
import unittest
import shutil
from unittest.mock import patch

from runtime_environment import configure_runtime
configure_runtime()
from scripts.refresh_catalog_index import refresh_catalog
from scripts.activate_movie_expansion import INDEX_STATE_FILES, capture_source_generation, validate_resume_generation


class MovieGenerationResumeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.storage = Path(self.temporary.name)
        self.active = self.storage / "data/index"
        self.generation = self.storage / "artifacts/index_generations/example"
        self.active.mkdir(parents=True)
        for name in INDEX_STATE_FILES:
            (self.active / name).write_bytes(b"unchanged source")
        shutil.copytree(self.active, self.generation / "prepared")
        capture_source_generation(self.generation, self.active, verify_copy=True)

    def test_only_matching_active_source_can_resume(self):
        self.assertEqual(validate_resume_generation(self.generation, self.storage, self.active), self.generation)
        (self.active / INDEX_STATE_FILES[0]).write_bytes(b"new active source")
        with self.assertRaisesRegex(ValueError, "changed"):
            validate_resume_generation(self.generation, self.storage, self.active)

    def test_installed_or_external_generations_cannot_resume(self):
        (self.generation / "previous").mkdir()
        with self.assertRaisesRegex(ValueError, "uninstalled"):
            validate_resume_generation(self.generation, self.storage, self.active)
        with self.assertRaisesRegex(ValueError, "inside storage"):
            validate_resume_generation(self.storage, self.storage, self.active)


class MovieIndexTests(unittest.TestCase):
    def test_verified_narrative_precedes_legacy_production_text_and_keeps_identity(self):
        from build_index_v2 import IndexBuilderV2
        builder = IndexBuilderV2.__new__(IndexBuilderV2)
        movie = {"id": 99, "title": "Example", "wiki_plot": "A witness discovers a hidden letter.",
                 "overview": "Production and awards information.", "rich_text": "Title: Example | Awards: irrelevant metadata",
                 "evidence_sources": [{"revision_id": 123}]}
        text = builder._movie_document(movie)
        self.assertTrue(text.startswith("Title: Example | Plot: A witness discovers"))
        self.assertNotIn("Awards:", text)
        self.assertEqual(builder.prepare_metadata([movie])[0]["overview"], movie["overview"])
        movie.pop("evidence_sources")
        self.assertEqual(builder._movie_document(movie), movie["rich_text"])

    def test_a_movie_literally_named_unknown_is_not_an_empty_title(self):
        from build_index_v2 import has_movie_title
        self.assertTrue(has_movie_title({"title": "Unknown"}))
        self.assertTrue(has_movie_title({"original_title": "Unknown"}))
        self.assertFalse(has_movie_title({"title": "  ", "original_title": None}))

    def setUp(self):
        import faiss
        import numpy as np
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        for name, dim, count in (("faiss_index_v2.bin", 3, 2), ("multilingual.index", 2, 3)):
            index = faiss.IndexFlatIP(dim)
            index.add(np.ones((count, dim), dtype="float32"))
            faiss.write_index(index, str(self.folder / name))
        metadata = [{"id": 1, "title": "Old", "overview": "Old story"},
                    {"id": "episode:1", "record_type": "episode", "parent_id": "series:1", "overview": "Episode text"}]
        (self.folder / "metadata_v2.pkl").write_bytes(pickle.dumps(metadata))
        (self.folder / "multilingual_metadata.json").write_text(json.dumps(["title:1", "episode:episode:1", "scene:real:1"]))
        (self.folder / "multilingual_report.json").write_text(json.dumps({"model": "toy-e5"}))
        (self.folder / "index_report.json").write_text("{}")
        self.documents = [{"id": 1, "title": "A film", "overview": "New synopsis", "release_year": "2024",
                           "story_passages": ["A detective discovers a hidden key."]},
                          {"id": 2, "title": "Another film", "overview": "Another story", "release_year": "2025"}]

    @staticmethod
    def encoder(model, length):
        import numpy as np
        class Encoder:
            def encode(self, texts, batch_size):
                return np.full((len(texts), 3 if "bge" in model else 2), 2, dtype="float32")
        return Encoder()

    def test_changed_and_new_films_preserve_episodes_and_real_scene_vectors(self):
        import faiss
        import numpy as np
        from multilingual_index import title_passages
        with patch("core.resource_budget.check_model_budget"):
            result = refresh_catalog(self.folder, self.documents, self.encoder)
            self.assertEqual(result["changed_titles"], 2)
            self.assertEqual(refresh_catalog(self.folder, self.documents, self.encoder), {"changed_titles": 0})
        metadata = pickle.loads((self.folder / "metadata_v2.pkl").read_bytes())
        self.assertEqual([row["id"] for row in metadata], [1, "episode:1", 2])
        keys = json.loads((self.folder / "multilingual_metadata.json").read_text())
        self.assertEqual(keys.count("title:1"), len(title_passages(metadata[0])))
        self.assertEqual(keys[:2], ["episode:episode:1", "scene:real:1"])
        np.testing.assert_array_equal(faiss.read_index(str(self.folder / "multilingual.index")).reconstruct(1), np.ones(2))
        np.testing.assert_array_equal(faiss.read_index(str(self.folder / "faiss_index_v2.bin")).reconstruct(1), np.ones(3))

    def test_failed_second_encoder_does_not_write_any_index_artifact(self):
        original = {p.name: p.read_bytes() for p in self.folder.iterdir()}
        def fail(model, length):
            if model == "toy-e5":
                raise RuntimeError("simulated model failure")
            return self.encoder(model, length)
        with patch("core.resource_budget.check_model_budget"), self.assertRaisesRegex(RuntimeError, "simulated"):
            refresh_catalog(self.folder, self.documents, fail)
        self.assertEqual(original, {p.name: p.read_bytes() for p in self.folder.iterdir()})

    def test_document_only_refresh_reuses_identical_multilingual_artifacts(self):
        with patch("core.resource_budget.check_model_budget"):
            refresh_catalog(self.folder, self.documents, self.encoder)
            before = {name: (self.folder / name).read_bytes() for name in ("multilingual.index", "multilingual_metadata.json")}
            documents = [{**document, "rich_text": "Title: revised encoder representation"} for document in self.documents]
            with patch.object(self, "encoder", wraps=self.encoder) as factory:
                result = refresh_catalog(self.folder, documents, factory)
            self.assertEqual(result["refreshed_story_passages"], 0)
            self.assertEqual(factory.call_count, 1)
            self.assertIn("bge", factory.call_args.args[0])
        self.assertEqual(before, {name: (self.folder / name).read_bytes() for name in before})


if __name__ == "__main__":
    unittest.main()
