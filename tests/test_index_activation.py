import json
import importlib.util
from pathlib import Path
import pickle
import shutil
import tempfile
import unittest
from unittest.mock import patch

from runtime_environment import configure_runtime
configure_runtime()
from scripts.activate_series_expansion import CATALOG_FILES, install_generation, validate_candidate, validate_indexes


class IndexActivationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.storage = Path(self.temporary.name)
        self.active = self.storage / "data/index"
        self.prepared = self.storage / "generations/prepared"
        self.backup = self.storage / "generations/previous"
        self.candidate = self.storage / "candidate"
        self.catalogs = self.storage / "data/processed"
        for folder in (self.active, self.prepared, self.candidate, self.catalogs):
            folder.mkdir(parents=True)
        (self.active / "version").write_text("old")
        (self.prepared / "version").write_text("new")
        for name in CATALOG_FILES:
            (self.candidate / name).write_text("new")
            (self.catalogs / name).write_text("old")

    def install(self):
        install_generation(self.prepared, self.active, self.candidate, self.catalogs, self.backup, self.storage)

    def test_activation_preserves_previous_generation(self):
        self.install()
        self.assertEqual((self.active / "version").read_text(), "new")
        self.assertEqual((self.backup / "index/version").read_text(), "old")
        self.assertTrue(all((self.catalogs / name).read_text() == "new" for name in CATALOG_FILES))

    def test_failed_catalog_copy_rolls_back_index_and_new_catalog(self):
        (self.catalogs / CATALOG_FILES[0]).unlink()
        copy = shutil.copy2

        def fail(source, target, **kwargs):
            if Path(source) == self.candidate / CATALOG_FILES[1]:
                raise OSError("simulated interrupted installation")
            return copy(source, target, **kwargs)

        with patch("scripts.activate_series_expansion.shutil.copy2", side_effect=fail):
            with self.assertRaisesRegex(OSError, "interrupted"):
                self.install()
        self.assertEqual((self.active / "version").read_text(), "old")
        self.assertFalse((self.catalogs / CATALOG_FILES[0]).exists())
        self.assertEqual((self.catalogs / CATALOG_FILES[1]).read_text(), "old")
        self.assertEqual(list(self.catalogs.glob("*.installing")), [])

    def test_destinations_outside_storage_are_rejected_before_moves(self):
        self.backup = self.storage.parent / "outside-storage"
        with self.assertRaisesRegex(ValueError, "inside"):
            self.install()
        self.assertEqual((self.active / "version").read_text(), "old")

    def test_overlapping_index_destinations_are_rejected(self):
        self.backup = self.prepared / "nested"
        with self.assertRaisesRegex(ValueError, "separate"):
            self.install()

    def test_invalid_episode_provenance_is_rejected(self):
        (self.candidate / "tv_series_enriched.json").write_text(json.dumps([{"id": "show"}]))
        (self.candidate / "tv_episodes_enriched.json").write_text(json.dumps([
            {"id": "episode", "parent_id": "show", "record_type": "episode", "scene_timeline": [{"start_sec": 4}]}
        ]))
        with self.assertRaisesRegex(ValueError, "provenance"):
            validate_candidate(self.candidate)

    def test_aliases_require_attributed_identity_evidence_before_activation(self):
        (self.candidate / "tv_series_enriched.json").write_text(json.dumps([
            {"id": "legacy", "external_tvmaze": "42", "id_aliases": ["duplicate"]}]))
        (self.candidate / "tv_episodes_enriched.json").write_text("[]")
        with self.assertRaisesRegex(ValueError, "source/cast evidence"):
            validate_candidate(self.candidate)

    @unittest.skipUnless(importlib.util.find_spec("faiss"), "Optional FAISS runtime not installed")
    def test_proven_alias_reconciliation_preserves_vectors_and_reparents_episodes(self):
        import faiss
        import numpy as np
        from scripts.reconcile_index_identities import reconcile_indexes
        metadata = [{"id": "legacy"}, {"id": "duplicate"}, {"id": "episode", "record_type": "episode", "parent_id": "duplicate"}]
        for name, dimension in (("faiss_index_v2.bin", 1024), ("multilingual.index", 768)):
            index = faiss.IndexFlatIP(dimension)
            index.add(np.repeat(np.arange(3, dtype="float32")[:, None], dimension, axis=1))
            faiss.write_index(index, str(self.prepared / name))
        (self.prepared / "metadata_v2.pkl").write_bytes(pickle.dumps(metadata))
        (self.prepared / "multilingual_metadata.json").write_text(json.dumps(["title:legacy", "title:duplicate", "episode:episode"]))
        for name in ("multilingual_report.json", "index_report.json"):
            (self.prepared / name).write_text("{}")
        documents = [{"id": "legacy", "id_aliases": ["duplicate"]}, {"id": "episode"}]
        report = reconcile_indexes(self.prepared, documents)
        self.assertEqual(report, {"removed_title_records": 1, "reparented_episodes": 1})
        result = pickle.loads((self.prepared / "metadata_v2.pkl").read_bytes())
        self.assertEqual([row["id"] for row in result], ["legacy", "episode"])
        self.assertEqual(result[1]["parent_id"], "legacy")
        np.testing.assert_array_equal(faiss.read_index(str(self.prepared / "faiss_index_v2.bin")).reconstruct(1), np.full(1024, 2))
        self.assertEqual(json.loads((self.prepared / "multilingual_metadata.json").read_text()), ["title:legacy", "episode:episode"])
        self.assertEqual(reconcile_indexes(self.prepared, documents)["removed_title_records"], 0)
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            reconcile_indexes(self.prepared, [{"id": "legacy", "id_aliases": ["duplicate"]}, {"id": "other", "id_aliases": ["duplicate"]}])

    @unittest.skipUnless(importlib.util.find_spec("faiss"), "Optional FAISS runtime not installed")
    def test_index_validation_checks_record_membership_and_candidate_completeness(self):
        import faiss
        import numpy as np
        for name, dimension in (("faiss_index_v2.bin", 1024), ("multilingual.index", 768)):
            index = faiss.IndexFlatIP(dimension)
            index.add(np.zeros((1, dimension), dtype="float32"))
            faiss.write_index(index, str(self.prepared / name))
        faiss.write_index(faiss.IndexFlatIP(1024), str(self.prepared / "scenes.index"))
        (self.prepared / "metadata_v2.pkl").write_bytes(pickle.dumps([{"id": "show"}]))
        (self.prepared / "scene_metadata.pkl").write_bytes(pickle.dumps([]))
        keys = self.prepared / "multilingual_metadata.json"
        keys.write_text(json.dumps(["title:show"]))
        self.assertEqual(validate_indexes(self.prepared)["parent_titles"], 1)
        keys.write_text(json.dumps(["scene:unknown"]))
        with self.assertRaisesRegex(ValueError, "unknown record"):
            validate_indexes(self.prepared)
        keys.write_text(json.dumps(["title:show"]))
        (self.candidate / "episode_expansion_documents.json").write_text(json.dumps([{"id": "missing"}]))
        with self.assertRaisesRegex(ValueError, "missing candidate"):
            validate_indexes(self.prepared, self.candidate)


if __name__ == "__main__":
    unittest.main()
