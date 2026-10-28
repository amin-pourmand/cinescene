import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from backend.media_worker import PREFIX, crawl_in_worker


class MediaWorkerTests(unittest.TestCase):
    def setUp(self):
        budget = patch("backend.media_worker.check_model_budget")
        job = patch("backend.media_worker.WorkerJob")
        self.budget = budget.start()
        self.job = job.start()
        self.addCleanup(budget.stop)
        self.addCleanup(job.stop)

    def process(self, events, code=0):
        process = Mock()
        process.stdin = io.StringIO()
        process.stdout = io.StringIO("unstructured library output\n" + "".join(PREFIX + json.dumps(event) + "\n" for event in events))
        process.wait.return_value = code
        process.poll.return_value = code
        return process

    def test_progress_and_report_are_structured_and_process_is_reaped(self):
        process = self.process([{"type": "progress", "value": {"stage": "vision", "overall_fraction": .5}},
                                {"type": "report", "value": {"documents_created": 1}}])
        progress = Mock()
        with tempfile.TemporaryDirectory() as folder, patch("backend.media_worker.ROOT", Path(folder)), patch("backend.media_worker.subprocess.Popen", return_value=process):
            result = crawl_in_worker("videos", enable_vision=True, progress_callback=progress)
        self.assertEqual(result["documents_created"], 1)
        progress.assert_called_once_with({"stage": "vision", "overall_fraction": .5})
        process.wait.assert_called_once()
        self.assertTrue(process.stdout.closed)
        self.budget.assert_called_once_with(required_mb=3072)
        self.job.return_value.close.assert_called_once()

    def test_missing_report_is_not_success(self):
        process = self.process([], 2)
        with tempfile.TemporaryDirectory() as folder, patch("backend.media_worker.ROOT", Path(folder)), patch("backend.media_worker.subprocess.Popen", return_value=process):
            with self.assertRaisesRegex(RuntimeError, "worker failed"):
                crawl_in_worker("videos")

    def test_callback_failure_terminates_child(self):
        process = self.process([{"type": "progress", "value": {}}])
        process.poll.return_value = None
        with tempfile.TemporaryDirectory() as folder, patch("backend.media_worker.ROOT", Path(folder)), patch("backend.media_worker.subprocess.Popen", return_value=process):
            with self.assertRaisesRegex(ValueError, "callback failed"):
                crawl_in_worker("videos", progress_callback=Mock(side_effect=ValueError("callback failed")))
        process.terminate.assert_called_once()
        process.wait.assert_called_once_with(timeout=10)

    def test_low_memory_refuses_a_media_worker_before_spawning(self):
        from core.resource_budget import ResourceBudgetError
        self.budget.side_effect = ResourceBudgetError("insufficient RAM")
        with patch("backend.media_worker.subprocess.Popen") as spawn:
            with self.assertRaises(ResourceBudgetError):
                crawl_in_worker("videos", enable_vision=True)
            spawn.assert_not_called()
