import unittest
import importlib.util
from pathlib import Path

from core.public_retrieval import catalog_passages, relevance_text
from query_processor import QueryProcessor


class QueryIntentTests(unittest.TestCase):
    def setUp(self):
        self.processor = QueryProcessor()

    def test_narrative_dates_and_title_numbers_are_not_release_filters(self):
        for query in ("2001: A Space Odyssey", "a soldier fights in 1944", "aliens arrive in 2015"):
            self.assertIsNone(self.processor.extract_filters(query)["year_range"])
            self.assertEqual(self.processor.clean_query(query), query)

    def test_explicit_release_filters_and_negated_genres(self):
        result = self.processor.process("science fiction from 2014 without horror")
        self.assertEqual(result["filters"]["year_range"], (2014, 2014))
        self.assertEqual(result["filters"]["excluded_genres"], ["Horror"])
        self.assertNotIn("Horror", result["filters"]["genres"])
        self.assertIsNone(self.processor.extract_filters("someone is killed by John Smith")["director"])

    def test_persian_digits_and_explicit_year(self):
        result = self.processor.process("فیلم محصول ۲۰۱۴")
        self.assertEqual(result["filters"]["year_range"], (2014, 2014))


class PassageEvidenceTests(unittest.TestCase):
    def test_reranker_uses_metadata_and_does_not_duplicate_summary(self):
        item = {"title": "Example", "year": "2020", "genres": ["Drama"], "keywords": ["memory"], "overview": "A short plot."}
        text = relevance_text(item, "Example (2020). A short plot.")
        self.assertEqual(text.count("A short plot."), 1)
        self.assertIn("Genres: Drama", text)
        self.assertIn("Keywords: memory", text)
        self.assertIn("Evidence: A later event", relevance_text(item, "A later event"))
    def test_title_only_records_remain_indexable_without_invented_story(self):
        records = catalog_passages([{"title": "A title without a plot"}])
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["kind"], "title")

    def test_story_is_not_relabelled_as_an_extracted_scene(self):
        records = catalog_passages([{"title": "Example", "overview": "A story.", "plot": "Another event.",
                                     "scene_timeline": [{"transcript": "Actual dialogue", "start_sec": 12}]}])
        self.assertEqual([row["kind"] for row in records], ["story", "story", "scene"])
        self.assertIsNone(records[0]["scene"])
        self.assertEqual(records[-1]["scene"], 0)

    def test_public_export_never_admits_private_uploads(self):
        from scripts.build_pwa_catalog import can_publish_media
        self.assertFalse(can_publish_media({"title": "A private family video", "source": "offline_video_ingestion"}))

    def test_search_request_defaults_to_reranking(self):
        from backend.main import SearchRequest
        self.assertTrue(SearchRequest(query="a remembered scene").use_reranking)

    def test_browser_has_no_silent_keyword_fallback(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "docs/assets/app.js").read_text(encoding="utf-8")
        self.assertIn("state.semantic.search", source)
        self.assertNotIn("function scoreItem", source)
        self.assertNotIn("function searchCatalog", source)
        self.assertIn("Semantic search could not load", source)


@unittest.skipUnless(importlib.util.find_spec("numpy"), "Optional numerical runtime is not installed")
class PassageRankingTests(unittest.TestCase):
    def setUp(self):
        import numpy as np
        from core.passage_search import PassageSearchEngine
        self.engine = PassageSearchEngine.__new__(PassageSearchEngine)
        self.engine.metadata = [{"id": 1, "title": "Story", "media_type": "movie", "overview": "A story", "scene_timeline": []},
                                {"id": 2, "title": "Scene", "media_type": "series", "overview": "", "scene_timeline": [{"transcript": "Actual dialogue", "start_sec": 12}]}]
        self.engine.passages = [{"item": 0, "kind": "story", "scene": None, "text": "Story evidence"},
                                {"item": 0, "kind": "story", "scene": None, "text": "Weaker story"},
                                {"item": 1, "kind": "scene", "scene": 0, "text": "Scene evidence"}]
        self.engine.vectors = np.array([[.9, 0], [.85, 0], [.8, 0]], dtype=np.float32)
        self.engine.query_processor = QueryProcessor()
        self.engine.cross_encoder = None
        class Encoder:
            def encode(self, text):
                return np.array([1, 0], dtype=np.float32)
        self.engine.model = Encoder()

    def test_title_maxpool_and_real_evidence(self):
        results = self.engine.search("a remembered moment")
        self.assertEqual([row["title"] for row in results], ["Story", "Scene"])
        self.assertEqual(results[0]["evidence"], "Story evidence")
        self.assertIsNone(results[0]["matched_scene"])
        self.assertEqual(results[1]["matched_scene"]["start_sec"], 12)

    def test_scene_scope_never_returns_story_only_records(self):
        results = self.engine.search("a remembered moment", scope="scenes")
        self.assertEqual([row["title"] for row in results], ["Scene"])

    def test_media_filter_is_applied_before_shortlisting(self):
        results = self.engine.search("a remembered moment", media_type="series")
        self.assertEqual([row["title"] for row in results], ["Scene"])

    def test_reranking_preserves_raw_score_order_without_mixing_cosine(self):
        class Reranker:
            def predict(self, pairs, **kwargs):
                return [-8, -2]
        self.engine.cross_encoder = Reranker()
        self.assertEqual(self.engine.search("a remembered moment")[0]["title"], "Scene")

    def test_persian_queries_do_not_use_english_only_reranker(self):
        class Reranker:
            def predict(self, pairs):
                raise AssertionError("English-only reranker must not score Persian text")
        self.engine.cross_encoder = Reranker()
        self.assertEqual(self.engine.search("یک لحظه به یاد مانده")[0]["title"], "Story")
