"""Ranking invariants without loading weights; skipped in the lightweight API CI."""

import importlib.util
import unittest


AVAILABLE = importlib.util.find_spec("sentence_transformers") is not None and importlib.util.find_spec("faiss") is not None


@unittest.skipUnless(AVAILABLE, "Optional model libraries are not installed")
class RankingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from hybrid_search import HybridSearchEngine

        cls.engine_class = HybridSearchEngine

    def setUp(self):
        self.engine = self.engine_class.__new__(self.engine_class)

    def test_duplicate_lexical_candidates_are_not_counted_twice(self):
        fused = dict(self.engine.reciprocal_rank_fusion([], [(0, 1), (0, .5), (1, .2)]))
        self.assertAlmostEqual(fused[0], 1 / 61)

    def test_zero_overlap_does_not_return_arbitrary_documents(self):
        self.engine.metadata = [{}, {}]
        self.engine.lexical_docs = [["dream"], ["detective"]]
        self.engine.bm25 = None
        self.assertEqual(self.engine.lexical_search("dinosaurs"), [])

    def test_persian_tokens_are_normalized_and_function_words_ignored(self):
        self.assertEqual(self.engine._lexical_tokens("كارآگاه فیلم شده است"), ["کارآگاه"])

    def test_many_weak_scenes_do_not_beat_a_better_title_match(self):
        self.engine.metadata = [
            {"id": "movie", "title": "Relevant"},
            *[{"parent_id": "long-film", "record_type": "scene", "matched_scene": {"scene_number": i}} for i in range(8)],
        ]
        candidates = [(0, .02)] + [(i, .019) for i in range(1, 9)]
        collapsed = self.engine._collapse_titles(candidates)
        self.assertEqual(collapsed[0][0], 0)
        self.assertEqual(collapsed[1][1], .019)

    def test_media_filter_preserves_only_requested_type(self):
        self.engine.metadata = [{"media_type": "movie"}, {"media_type": "series"}]
        self.assertEqual(self.engine.apply_filters([(0, 1), (1, .9)], {"media_type": "series"}), [(1, .9)])

    def test_episode_evidence_collapses_to_parent_without_fake_scene(self):
        self.engine.metadata = [{"id": "episode:1", "parent_id": "show:1", "record_type": "episode", "title": "A Show",
                                 "overview": "An episode event", "matched_episode": {"season": 2, "episode": 3}}]
        self.engine.parent_metadata = {"show:1": {"id": "show:1", "title": "A Show", "overview": "Series synopsis"}}
        result = self.engine._format_result(0, 1, 1)
        self.assertEqual(result["id"], "show:1")
        self.assertEqual(result["evidence"], "An episode event")
        self.assertEqual(result["matched_episode"]["episode"], 3)
        self.assertIsNone(result["matched_scene"])

    def test_unscored_fusion_values_do_not_jump_above_negative_reranker_logits(self):
        class FakeReranker:
            def predict(self, pairs, **kwargs):
                return [-5, -2]

        self.engine.cross_encoder = FakeReranker()
        self.engine.metadata = [{"title": "A"}, {"title": "B"}, {"title": "C"}]
        rows = self.engine.rerank_titles("query", [(0, .03, []), (1, .02, []), (2, .01, [])], limit=2)
        self.assertEqual([row[0] for row in rows], [1, 0, 2])

    def test_reranker_receives_retrieved_story_and_series_context(self):
        captured = []
        class FakeReranker:
            def predict(self, pairs, **kwargs):
                captured.extend(pairs)
                return [1]
        self.engine.cross_encoder = FakeReranker()
        self.engine.metadata = [{"title": "Show", "parent_id": "show", "overview": "Episode event"}]
        self.engine.parent_metadata = {"show": {"overview": "Series premise"}}
        self.engine.rerank_titles("query", [(0, .1, [])], evidence={0: "A detailed event beyond the short summary"})
        self.assertIn("Series premise", captured[0][1])
        self.assertIn("A detailed event beyond", captured[0][1])

    def test_episode_filters_use_authoritative_parent_genres(self):
        self.engine.metadata = [{"parent_id": "show", "genres": ["TV Dramas"]}]
        self.engine.parent_metadata = {"show": {"genres": ["Science Fiction"]}}
        self.assertEqual(self.engine.apply_filters([(0, 1)], {"genres": ["Science Fiction"]}), [(0, 1)])


if __name__ == "__main__":
    unittest.main()
