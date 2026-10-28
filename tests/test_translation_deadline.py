import os
import unittest
from unittest.mock import PropertyMock, patch

from core.query_translation import OfflineQueryTranslator


class TranslationDeadlineTests(unittest.TestCase):
    def test_configured_deadline_reaches_query_and_evidence_workers_without_relaxing_memory(self):
        with patch.dict(os.environ, {"CINESCENE_TRANSLATION_TIMEOUT_SEC": "150"}), \
             patch.object(OfflineQueryTranslator, "available", new_callable=PropertyMock, return_value=True), \
             patch("core.model_worker.run_worker", return_value="Translated text") as worker:
            translator = OfflineQueryTranslator()
            translator.translate("query")
            translator.translate_evidence("dialogue")
            self.assertEqual(worker.call_count, 2)
            for call in worker.call_args_list:
                self.assertEqual(call.kwargs["timeout"], 150)
                self.assertEqual(call.kwargs["required_mb"], 850)
            self.assertEqual(translator.status()["timeout_seconds"], 150)

    def test_deadlines_remain_bounded(self):
        for value, expected in (("1", 30), ("999", 300)):
            with patch.dict(os.environ, {"CINESCENE_TRANSLATION_TIMEOUT_SEC": value}):
                self.assertEqual(OfflineQueryTranslator().timeout, expected)
