"""Language routing and passage selection invariants; no model weights required."""
import importlib.util
import os
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest.mock import Mock, patch

from core.query_translation import OfflineQueryTranslator, translation_python
from core.resource_budget import ResourceBudgetError, check_model_budget


class ResourceBudgetTests(unittest.TestCase):
    def test_low_system_space_blocks_before_memory_probe(self):
        with patch("core.resource_budget.shutil.disk_usage") as disk, patch("core.resource_budget.memory_headroom") as memory:
            disk.return_value.free = 1024 ** 3
            with self.assertRaises(ResourceBudgetError):
                check_model_budget()
            memory.assert_not_called()

    def test_available_commit_and_physical_memory_are_both_checked(self):
        with patch("core.resource_budget.shutil.disk_usage") as disk, patch("core.resource_budget.memory_headroom") as memory:
            disk.return_value.free = 10 * 1024 ** 3
            for ram, commit in ((300, 4000), (4000, 300)):
                memory.return_value = {"available_ram_mb": ram, "available_commit_mb": commit}
                with self.assertRaises(ResourceBudgetError):
                    check_model_budget(768)
            memory.return_value = {"available_ram_mb": 4000, "available_commit_mb": 4000}
            self.assertEqual(check_model_budget(768), memory.return_value)

    def test_reranker_ablation_collapses_parent_titles_without_losing_winning_episode(self):
        from scripts.compare_reranker import rank_distinct_candidates
        candidates = [{"id": "show", "matched_episode": {"episode": 1}},
                      {"id": "show", "matched_episode": {"episode": 2}}, {"id": "another"}]
        result = rank_distinct_candidates([-2, 3, 2], candidates)
        self.assertEqual([row["id"] for row in result], ["show", "another"])
        self.assertEqual(result[0]["matched_episode"]["episode"], 2)
        with self.assertRaises(ValueError):
            rank_distinct_candidates([1], candidates)


class TranslationTests(unittest.TestCase):
    def test_missing_translation_is_explicit_and_does_not_download(self):
        with patch.dict(os.environ, {"CINESCENE_TRANSLATION_MODEL": "a-model-that-is-not-installed"}):
            translator = OfflineQueryTranslator()
            self.assertIsNone(translator.translate("a sentence"))
            self.assertFalse(translator.status()["available"])
            self.assertFalse(translator.status()["external_query_requests"])

    def test_worker_receives_the_complete_query_and_caches_only_in_memory(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"CINESCENE_TRANSLATION_MODEL": folder}):
            for name in ("model.bin", "config.json", "tokenizer.json"):
                (Path(folder) / name).touch()
            translator = OfflineQueryTranslator()
            translator.executable = Path(__file__)
            with patch("core.model_worker.run_worker", return_value="A person returns before the accident.") as worker:
                text = "یک نفر قبل از حادثه برمیگرده نه بعدش"
                self.assertEqual(translator.translate(text), "A person returns before the accident.")
                translator.translate(text)
                self.assertEqual(worker.call_count, 1)
                self.assertEqual(worker.call_args.args[0]["text"], text)

    def test_translation_runtime_uses_configured_storage(self):
        with patch.dict(os.environ, {"CINESCENE_STORAGE_ROOT": "alternate-storage"}):
            self.assertIn("alternate-storage", str(translation_python()))

    def test_evidence_translation_is_bounded_and_caches_separately_from_queries(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"CINESCENE_TRANSLATION_MODEL": folder}):
            for name in ("model.bin", "config.json", "tokenizer.json"):
                (Path(folder) / name).touch()
            translator = OfflineQueryTranslator()
            translator.executable = Path(__file__)
            with patch("core.model_worker.run_worker", return_value="The witness hides the blue letter.") as worker:
                translator.translate_evidence("شاهد نامه آبی را پنهان می کند")
                translator.translate_evidence("شاهد نامه آبی را پنهان می کند")
                self.assertEqual(worker.call_count, 1)
                self.assertTrue(worker.call_args.args[0]["truncate"])


class WorkerProtocolTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Windows launcher contract")
    def test_windows_uses_real_python_and_only_the_chosen_environment(self):
        from core.model_worker import worker_launch
        import sys
        executable = Path("E:/isolated-worker/Scripts/python.exe")
        command, environment = worker_launch("core.model_worker", executable)
        self.assertEqual(command[0], sys._base_executable)
        self.assertEqual(command[1], "-S")
        self.assertIn("isolated-worker", environment["PYTHONPATH"])
        self.assertEqual(environment["CT2_PACKED_GEMM"], "0")

    def worker(self, output='{"value": [1]}', code=0):
        process = Mock()
        process.communicate.return_value = (output, "private diagnostic")
        process.returncode = code
        process.poll.return_value = code
        return process

    def test_budget_is_checked_before_spawning(self):
        from core.model_worker import run_worker
        with patch("core.model_worker.check_model_budget", side_effect=ResourceBudgetError("low")), patch("core.model_worker.subprocess.Popen") as spawn:
            with self.assertRaises(ResourceBudgetError):
                run_worker({"kind": "embed"})
            spawn.assert_not_called()

    def test_worker_result_and_job_cleanup(self):
        from core.model_worker import run_worker
        process, job = self.worker(), Mock()
        with patch("core.model_worker.check_model_budget"), patch("core.model_worker.subprocess.Popen", return_value=process), patch("core.model_worker.WorkerJob", return_value=job):
            self.assertEqual(run_worker({"kind": "embed"}), [1])
            job.close.assert_called_once()
            process.kill.assert_not_called()

    def test_bad_response_and_failure_are_not_success(self):
        from core.model_worker import ModelWorkerError, run_worker
        for output, code in (("not json", 0), ('{"no_value": true}', 0), ("[]", 0), ("null", 0), ("", 1)):
            job = Mock()
            with patch("core.model_worker.check_model_budget"), patch("core.model_worker.subprocess.Popen", return_value=self.worker(output, code)), patch("core.model_worker.WorkerJob", return_value=job):
                with self.assertRaises(ModelWorkerError) as error:
                    run_worker({"kind": "embed"})
                self.assertNotIn("private diagnostic", str(error.exception))
                job.close.assert_called_once()

    def test_timeout_reaps_the_process_and_closes_the_job(self):
        from core.model_worker import ModelWorkerError, run_worker
        process, job = self.worker(), Mock()
        process.communicate.side_effect = [subprocess.TimeoutExpired("worker", 1), ("", "")]
        process.poll.return_value = None
        with patch("core.model_worker.check_model_budget"), patch("core.model_worker.subprocess.Popen", return_value=process), patch("core.model_worker.WorkerJob", return_value=job):
            with self.assertRaises(ModelWorkerError):
                run_worker({"kind": "embed"}, timeout=1)
            job.close.assert_called_once()
            process.kill.assert_called_once()

    def test_api_memory_rejection_is_503_and_does_not_pollute_history(self):
        from backend.main import app
        from fastapi.testclient import TestClient
        engine = Mock()
        engine.search.side_effect = ResourceBudgetError("Insufficient memory")
        with patch("backend.main.get_search_engine", return_value=(engine, None)), patch("backend.main.memory.add_search") as history:
            response = TestClient(app).post("/api/search", json={"query": "a remembered scene"})
            self.assertEqual(response.status_code, 503)
            history.assert_not_called()

    def test_search_during_video_processing_does_not_load_another_model(self):
        from backend.main import app
        from fastapi.testclient import TestClient
        with patch("backend.main.PIPELINE_LOCK") as pipeline, patch("backend.main.get_search_engine") as loader:
            pipeline.locked.return_value = True
            response = TestClient(app).post("/api/search", json={"query": "a remembered scene"})
            self.assertEqual(response.status_code, 503)
            loader.assert_not_called()

    def test_scene_refresh_runs_in_a_bounded_worker(self):
        from backend.main import rebuild_scene_index_safely
        with patch.dict(os.environ, {"CINESCENE_SEARCH_ENGINE": "hybrid"}), \
             patch("backend.main.release_runtime_models"), patch("backend.main.clear_search_engine"), \
             patch("core.model_worker.run_worker", return_value={"scene_vectors": 3}) as worker:
            self.assertEqual(rebuild_scene_index_safely("local-model"), {"scene_vectors": 3})
            self.assertEqual(worker.call_args.kwargs["memory_mb"], 2048)
            self.assertEqual(worker.call_args.args[0]["kind"], "scene_refresh")

    def test_full_rebuild_checks_its_larger_budget_before_loading_any_weights(self):
        from backend.main import rebuild_all_indexes_safely
        with patch("backend.main.check_model_budget", side_effect=ResourceBudgetError("insufficient RAM")) as budget, \
             patch("build_index_v2.IndexBuilderV2") as loader:
            with self.assertRaises(ResourceBudgetError):
                rebuild_all_indexes_safely(Mock(), "unused-catalog")
            budget.assert_called_once_with(required_mb=4096)
            loader.assert_not_called()

    def test_transient_startup_budget_failure_is_not_cached_forever(self):
        import backend.main as api
        from core.resource_budget import ResourceBudgetError
        with patch.object(api, "SEARCH_ENGINE_LOADED", False), \
             patch.object(api, "SEARCH_ENGINE", None), patch.object(api, "SEARCH_ENGINE_ERROR", None), \
             patch("backend.main.check_model_budget", side_effect=ResourceBudgetError("low RAM")) as budget:
            self.assertEqual(api.get_search_engine(), (None, "low RAM"))
            self.assertFalse(api.SEARCH_ENGINE_LOADED)
            api.get_search_engine()
            self.assertEqual(budget.call_count, 2)


@unittest.skipUnless(importlib.util.find_spec("faiss"), "Optional FAISS runtime not installed")
class BilingualEvidenceTests(unittest.TestCase):
    def setUp(self):
        from hybrid_search import HybridSearchEngine
        from query_processor import QueryProcessor
        self.engine = HybridSearchEngine.__new__(HybridSearchEngine)
        self.engine.metadata = [
            {"id": "show", "title": "A show", "overview": "A general premise"},
            {"id": "ep1", "parent_id": "show", "record_type": "episode", "title": "A show", "overview": "A mistaken event", "matched_episode": {"episode": 1}},
            {"id": "ep2", "parent_id": "show", "record_type": "episode", "title": "A show", "overview": "A witness hides a letter", "matched_episode": {"episode": 2}},
            {"id": "other", "title": "Another title", "overview": "An unrelated event"},
        ]
        self.engine.parent_metadata = {"show": self.engine.metadata[0]}
        self.engine.story_windows = {}
        self.engine.bm25 = None
        self.engine.query_processor = QueryProcessor()

    def test_alternative_episode_can_win_after_evidence_reranking(self):
        class Reranker:
            def predict(self, pairs, **kwargs):
                return [10 if "witness hides" in text else -3 for query, text in pairs]
        self.engine.cross_encoder = Reranker()
        records = [(1, .04), (2, .03), (3, .02)]
        candidates = self.engine._collapse_titles(records)
        results = self.engine.rerank_titles("a witness hides a letter", candidates, evidence={}, records=records)
        self.assertEqual(results[0][0], 2)
        result = self.engine._format_result(*results[0][:2], rank=1)
        self.assertEqual(result["matched_episode"]["episode"], 2)
        self.assertIsNone(result["matched_scene"])

    def test_two_passages_are_scored_independently_before_max_pooling(self):
        captured = []
        class Reranker:
            def predict(self, pairs, **kwargs):
                captured.extend(pairs)
                return [10 if "clockwork bird" in text else -4 for query, text in pairs]
        self.engine.cross_encoder = Reranker()
        self.engine.story_windows = {0: ["A clockwork bird is hidden in a cupboard."]}
        evidence = {0: "A different opening event"}
        rows = self.engine.rerank_titles("clockwork bird cupboard", [(0, .04, []), (3, .03, [])], evidence=evidence, records=[(0, .04), (3, .03)])
        self.assertEqual(len(captured), 3)
        self.assertEqual(rows[0][0], 0)
        self.assertIn("clockwork bird", evidence[0])
        self.assertTrue(any("A general premise" in text for _, text in captured))
        self.assertFalse(any("clockwork bird" in text and "different opening" in text for _, text in captured))

    def test_a_story_winner_does_not_claim_an_unverified_scene_match(self):
        class Reranker:
            def predict(self, pairs, **kwargs):
                return [5, -5]
        self.engine.cross_encoder = Reranker()
        self.engine.metadata.append({"id": "scene", "parent_id": "show", "record_type": "scene", "matched_scene": {"transcript": "Something else", "start_sec": 10}})
        records = [(0, .04), (4, .03)]
        rows = self.engine.rerank_titles("query", self.engine._collapse_titles(records), evidence={}, records=records)
        self.assertEqual(rows[0][2], [])

    def test_offline_aggregate_cannot_replace_timed_evidence_or_leak_into_each_scene(self):
        captured = []
        class Reranker:
            def predict(self, pairs, **kwargs):
                captured.extend(pairs)
                return [5 if "letter" in text else -5 for _, text in pairs]
        self.engine.cross_encoder = Reranker()
        self.engine.metadata[0].update({"source": "offline_video_ingestion", "overview": "An aggregate about a hidden letter"})
        self.engine.metadata.extend([
            {"id": "scene1", "parent_id": "show", "record_type": "scene", "title": "A show", "matched_scene": {"transcript": "A witness hides a letter", "start_sec": 10}},
            {"id": "scene2", "parent_id": "show", "record_type": "scene", "title": "A show", "matched_scene": {"transcript": "A quiet road", "start_sec": 20}},
        ])
        records = [(0, .05), (4, .04), (5, .03)]
        rows = self.engine.rerank_titles("a hidden letter", self.engine._collapse_titles(records), evidence={}, records=records)
        self.assertEqual(rows[0][0], 4)
        self.assertEqual(rows[0][2][0]["start_sec"], 10)
        self.assertEqual(len(captured), 2)
        self.assertFalse(any("aggregate" in text for _, text in captured))

    def test_persian_scene_verification_uses_translation_without_replacing_original_evidence(self):
        captured = []
        class Reranker:
            def predict(self, pairs, **kwargs):
                captured.extend(pairs)
                return [5]
        self.engine.cross_encoder = Reranker()
        self.engine.translator = Mock()
        self.engine.translator.translate_evidence.return_value = "The witness hides a blue letter."
        original = "شاهد نامه آبی را پنهان می کند"
        self.engine.metadata.append({"id": "scene", "parent_id": "show", "record_type": "scene", "title": "A show",
                                     "matched_scene": {"transcript": original, "start_sec": 10}})
        records = [(4, .04)]
        result = self.engine.rerank_titles("a hidden letter", self.engine._collapse_titles(records), evidence={}, records=records)
        self.assertIn("witness hides a blue letter", captured[0][1])
        self.assertNotIn(original, captured[0][1])
        self.assertEqual(result[0][2][0]["transcript"], original)

    def test_original_persian_and_full_translation_reach_separate_channels(self):
        from unittest.mock import Mock
        self.engine.translator = Mock()
        self.engine.translator.translate.return_value = "A witness hides a letter before leaving."
        self.engine.multilingual = Mock()
        self.engine.multilingual.search.return_value = [(0, .9)]
        self.engine.vector_search = Mock(return_value=[(0, .9)])
        self.engine.lexical_search = Mock(return_value=[])
        self.engine.lexical_boost = Mock(side_effect=lambda query, rows: rows)
        self.engine.rerank_titles = Mock(side_effect=lambda query, rows, **kwargs: rows)
        query = "یه شاهد قبل از رفتن نامه رو قایم میکنه"
        self.engine.search(query)
        self.assertEqual(self.engine.multilingual.search.call_args.args[0], query)
        self.assertEqual(self.engine.vector_search.call_args.args[0], "A witness hides a letter before leaving.")
        self.assertEqual(self.engine.rerank_titles.call_args.args[0], "A witness hides a letter before leaving.")
        lexical_queries = [call.args[0] for call in self.engine.lexical_search.call_args_list]
        self.assertIn(query, lexical_queries)
        self.assertIn("A witness hides a letter before leaving.", lexical_queries)

    def test_original_dialogue_can_add_a_scene_missing_from_english_recall(self):
        self.engine.translator = Mock()
        self.engine.translator.translate.return_value = "a translated sentence"
        self.engine.multilingual = Mock()
        self.engine.multilingual.search.return_value = [(3, .9)]
        self.engine.vector_search = Mock(return_value=[(3, .9)])
        query = "یک شاهد نامه آبی را پنهان می کند"
        self.engine.metadata.append({"id": "scene", "parent_id": "show", "record_type": "scene",
                                     "matched_scene": {"transcript": query, "start_sec": 10}})
        self.engine.lexical_search = Mock(side_effect=lambda text, **kwargs: [(4, 8)] if text == query else [])
        self.engine.lexical_boost = Mock(side_effect=lambda text, rows: rows)
        rows = self.engine.search(query, use_reranking=False)
        self.assertIn("show", [row["id"] for row in rows])
        self.assertEqual(next(row for row in rows if row["id"] == "show")["matched_scene"]["transcript"], query)

    def test_a_few_common_persian_words_do_not_boost_a_scene_or_parent_overview(self):
        self.engine.metadata = [{"record_type": "scene"}, {"source": "offline_video_ingestion"}]
        self.engine.lexical_sets = [{"نامه"}, {"نامه", "آبی", "شاهد", "مخفی"}]
        self.engine.title_token_sets = [set(), set()]
        self.engine.transcript_token_sets = [{"نامه"}, set()]
        rows = self.engine.lexical_boost("شاهد نامه آبی مخفی", [(0, .01), (1, .01)])
        self.assertEqual(rows, [(0, .01), (1, .01)])

    def test_no_translation_never_sends_a_keyword_bag_to_english_models(self):
        from unittest.mock import Mock
        self.engine.translator = Mock()
        self.engine.translator.translate.return_value = None
        self.engine.multilingual = Mock()
        self.engine.multilingual.search.return_value = [(0, .9)]
        self.engine.vector_search = Mock()
        self.engine.lexical_search = Mock(return_value=[])
        self.engine.lexical_boost = Mock(side_effect=lambda query, rows: rows)
        self.engine.cross_encoder = None
        self.engine.search("افسر و سرباز دوباره تو جنگ زنده میشن")
        self.engine.vector_search.assert_not_called()
        self.assertEqual(self.engine.last_query["translation"], "unavailable")

    def test_translation_worker_failure_uses_original_multilingual_query_and_warns(self):
        from core.model_worker import ModelWorkerError
        self.engine.translator = Mock()
        self.engine.translator.translate.side_effect = ModelWorkerError("worker timed out")
        self.engine.multilingual = Mock()
        self.engine.multilingual.search.return_value = [(0, .9)]
        self.engine.vector_search = Mock()
        self.engine.lexical_search = Mock(return_value=[])
        self.engine.lexical_boost = Mock(side_effect=lambda query, rows: rows)
        self.engine.cross_encoder = Mock()
        query = "یک شاهد قبل از رفتن نامه را پنهان می کند"
        self.assertTrue(self.engine.search(query))
        self.engine.multilingual.search.assert_called_once()
        self.assertEqual(self.engine.multilingual.search.call_args.args[0], query)
        self.engine.vector_search.assert_not_called()
        self.engine.cross_encoder.predict.assert_not_called()
        self.assertEqual(self.engine.last_query["translation"], "failed")
        self.assertIn("without English reranking", self.engine.last_query["warning"])

    def test_translation_failure_without_a_multilingual_index_is_not_hidden(self):
        from core.model_worker import ModelWorkerError
        self.engine.translator = Mock()
        self.engine.translator.translate.side_effect = ModelWorkerError("worker failed")
        self.engine.multilingual = None
        with self.assertRaises(ModelWorkerError):
            self.engine.search("یک شاهد نامه را پنهان می کند")

    def test_low_disk_or_memory_still_stops_search_before_any_fallback(self):
        self.engine.translator = Mock()
        self.engine.translator.translate.side_effect = ResourceBudgetError("low disk")
        self.engine.multilingual = Mock()
        with self.assertRaises(ResourceBudgetError):
            self.engine.search("یک شاهد نامه را پنهان می کند")
        self.engine.multilingual.search.assert_not_called()


if __name__ == "__main__":
    unittest.main()
