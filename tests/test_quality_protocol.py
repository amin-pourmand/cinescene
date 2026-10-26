import hashlib
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend.main import app
from evaluation_metrics import normalize_title

ROOT = Path(__file__).resolve().parents[1]


class QualityProtocolTests(unittest.TestCase):
    def test_reserved_title_labels_are_disjoint_from_development(self):
        def labels(name):
            suite = json.loads((ROOT / "benchmarks" / name).read_text(encoding="utf-8"))
            return {normalize_title(title) for case in suite["cases"] for title in case["expected"]}
        self.assertFalse(labels("diverse-reserved-cases.json") & (labels("diverse-dev-cases.json") | labels("cases.json")))

    def test_development_suite_matches_the_frozen_policy(self):
        policy = json.loads((ROOT / "benchmarks/quality-policy.json").read_text(encoding="utf-8"))
        self.assertEqual(hashlib.sha256((ROOT / "benchmarks" / policy["development_suite"]).read_bytes()).hexdigest(),
                         policy["development_suite_sha256"])

    def test_invalid_searches_are_rejected_before_loading_models(self):
        client = TestClient(app)
        cases = [{"query": ""}, {"query": "   "}, {"query": "x" * 1001},
                 {"query": "a scene", "top_k": 0}, {"query": "a scene", "top_k": 21},
                 {"query": "a scene", "scope": "unknown"}, {"query": "a scene", "media_type": "tv"}]
        with patch("backend.main.get_search_engine") as loader:
            for payload in cases:
                with self.subTest(payload=payload):
                    self.assertEqual(client.post("/api/search", json=payload).status_code, 422)
            loader.assert_not_called()


if __name__ == "__main__":
    unittest.main()
