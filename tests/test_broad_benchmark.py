import json
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from scripts.broad_retrieval_benchmark import (
    check_system_space, coverage_matches, execute_case, expand_cases, judge_probe, report_metrics, result_identity, validate_targets,
)

ROOT = Path(__file__).resolve().parents[1]


class FakeResponse:
    def __init__(self, status, results=()):
        self.status_code, self.results = status, results

    def json(self):
        return {"results": list(self.results)}


class FakeClient:
    def __init__(self, response):
        self.response, self.payload = response, None

    def post(self, path, json):
        self.payload = json
        return self.response


class BroadBenchmarkTests(unittest.TestCase):
    def test_suite_counts_and_ids_are_stable(self):
        suite = json.loads((ROOT / "benchmarks/broad-scenarios.json").read_text(encoding="utf-8"))
        cases = expand_cases(suite)
        self.assertEqual(len(cases), 196)
        self.assertEqual(sum(row["kind"] == "retrieval" for row in cases), 160)
        self.assertEqual(len({row["id"] for row in cases}), 196)
        self.assertEqual(sum(row.get("pair") is not None for row in cases), 120)

    def test_duplicate_case_ids_fail_before_execution(self):
        with self.assertRaisesRegex(ValueError, "unique"):
            expand_cases({"topics": [], "additional": [{"id": "same"}, {"id": "same"}]})

    def test_coverage_distinguishes_remakes_but_not_provider_series_dates(self):
        movies = [{"id": "old", "title": "Dune", "media_type": "movie", "year": "1984"}]
        exact, versions = coverage_matches({"title": "Dune", "target_type": "movie", "year": "2021"}, movies)
        self.assertEqual(exact, [])
        self.assertEqual(len(versions), 1)
        exact, _ = coverage_matches({"title": "A Show", "target_type": "series", "year": "2000"},
                                    [{"id": "show", "title": "A Show", "media_type": "series", "year": "2019"}])
        self.assertEqual(len(exact), 1)

    def test_coverage_aliases_are_not_substring_matches(self):
        catalog = [{"id": 1, "title": "La Casa de Papel", "media_type": "series"},
                   {"id": 2, "title": "Money Heist: Korea", "media_type": "series"}]
        exact, _ = coverage_matches({"title": "Money Heist", "aliases": ["La Casa de Papel"], "target_type": "series"}, catalog)
        self.assertEqual([row["id"] for row in exact], [1])

    def test_identity_labels_and_episode_availability_are_checked(self):
        case = {"id": "case", "kind": "retrieval", "expected": ["A Show"], "expected_ids": ["show"], "season": 1, "episode": 2}
        with self.assertRaisesRegex(ValueError, "Episode absent"):
            validate_targets([case], [{"id": "show", "title": "A Show"}])
        with self.assertRaisesRegex(ValueError, "Title/ID"):
            validate_targets([{**case, "expected": ["Wrong"]}], [{"id": "show", "title": "A Show"}])

    def test_saved_results_contain_no_private_media_text_or_paths(self):
        row = result_identity({"id": 7, "title": "A Film", "source_video": "C:/private/movie.mp4", "overview": "Private text",
                               "matched_scene": {"transcript": "Private dialogue"}, "matched_episode": {"season": 1, "episode": 2, "summary": "Private text"}})
        self.assertNotIn("private", json.dumps(row).lower())
        self.assertEqual(row["matched_episode"], {"season": 1, "episode": 2})

    def test_wrong_episode_is_not_graded_as_a_correct_match(self):
        client = FakeClient(FakeResponse(200, [{"id": "show", "title": "Show", "matched_episode": {"season": 1, "episode": 3}}]))
        case = {"id": "episode", "kind": "retrieval", "query": "an event", "expected": ["Show"], "expected_ids": ["show"], "season": 1, "episode": 2}
        row = execute_case(client, case, [])
        self.assertIsNone(row["rank"])
        self.assertEqual(row["parent_rank"], 1)

    def test_negative_input_does_not_pass_on_server_failure(self):
        self.assertFalse(judge_probe("negative", 500, []))
        self.assertFalse(judge_probe("negative", 200, [{"id": "wrong"}]))
        self.assertTrue(judge_probe("negative", 200, []))
        self.assertFalse(judge_probe("ambiguous", 200, [{"id": 1}, {"id": 1}]))

    def test_malformed_success_response_is_not_mistaken_for_no_match(self):
        class BrokenResponse(FakeResponse):
            def json(self):
                raise ValueError("Malformed response")
        row = execute_case(FakeClient(BrokenResponse(200)), {"id": "bad", "kind": "negative", "query": "random letters"}, [])
        self.assertFalse(row["passed"])
        self.assertEqual(row["error"], "ValueError")

    def test_long_input_probe_sends_the_actual_invalid_payload(self):
        client = FakeClient(FakeResponse(422))
        row = execute_case(client, {"id": "long", "kind": "invalid", "payload": {"query_repeat": 1001}}, [])
        self.assertEqual(len(client.payload["query"]), 1001)
        self.assertTrue(row["passed"])

    def test_probe_failures_are_not_pooled_into_retrieval_metrics(self):
        base = {"kind": "retrieval", "category": "movie_plot", "provenance": "manual", "pair": "pair-1", "status": 200, "error": None, "latency_sec": 1}
        rows = [{**base, "language": "en", "rank": 1}, {**base, "language": "fa", "rank": 4},
                {"kind": "negative", "passed": False, "error": None}]
        metrics = report_metrics(rows)
        self.assertEqual(metrics["retrieval"]["cases"], 2)
        self.assertEqual(metrics["retrieval"]["hit_at_1"], .5)
        self.assertEqual(metrics["paired_topics"]["english_only_first"], 1)
        self.assertEqual(metrics["probes"]["negative"]["passed"], 0)

    def test_space_guard_stops_before_another_model_request(self):
        with patch("scripts.broad_retrieval_benchmark.shutil.disk_usage", return_value=SimpleNamespace(free=1024 ** 3)):
            with self.assertRaisesRegex(RuntimeError, "checkpoint preserved"):
                check_system_space(2, "/")
            check_system_space(0, "/")

    def test_report_table_escapes_user_supplied_separators(self):
        from scripts.summarize_broad_benchmark import cell, counts, table
        self.assertEqual(cell("a|b\nc"), "a\\|b c")
        self.assertEqual(counts([{"rank": 1}, {"rank": None}]), [2, 1, "50.0%", 1, "50.0%"])
        self.assertIn("a\\|b", "\n".join(table(["Query"], [["a|b"]])))

    def test_public_report_masks_private_identities_without_changing_metrics(self):
        from scripts.summarize_broad_benchmark import redact_private_results
        raw = {"retrieval": {"hit_at_1": .5}, "rows": [{"expected_ids": ["public"], "rank": 2,
               "results": [{"id": "secret", "title": "A personal title"}, {"id": "public", "title": "Public"}]}]}
        public = redact_private_results(raw, {"secret"})
        self.assertEqual(public["retrieval"], raw["retrieval"])
        self.assertEqual(public["rows"][0]["rank"], 2)
        self.assertNotIn("A personal title", json.dumps(public))
        self.assertEqual(raw["rows"][0]["results"][0]["id"], "secret")

    def test_private_targets_cannot_be_silently_published(self):
        from scripts.summarize_broad_benchmark import redact_private_results
        with self.assertRaisesRegex(ValueError, "target is private"):
            redact_private_results({"rows": [{"expected_ids": ["secret"]}]}, {"secret"})


if __name__ == "__main__":
    unittest.main()
