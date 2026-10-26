import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


@unittest.skipUnless(importlib.util.find_spec("faiss") and importlib.util.find_spec("onnxruntime"), "Optional inference runtime not installed")
class SceneIndexCacheTests(unittest.TestCase):
    def test_identical_scenes_reuse_vectors_but_changed_evidence_is_reencoded(self):
        import numpy as np
        import scene_index as module

        batches = []
        class Encoder:
            max_seq_length = 256
            def __init__(self, *args, **kwargs):
                pass
            def get_sentence_embedding_dimension(self):
                return 2
            def encode(self, texts, **kwargs):
                batches.append(texts)
                return np.array([[1, 0] for _ in texts], dtype=np.float32)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "catalog.json"
            rows = [{"id": "a", "title": "A", "scene_timeline": [
                {"scene_number": 1, "visual_caption": "A room", "start_sec": 0, "end_sec": 1},
                {"scene_number": 2, "visual_caption": "A street", "start_sec": 1, "end_sec": 2}]}]
            source.write_text(json.dumps(rows), encoding="utf-8")
            with patch.multiple(module, SCENE_INDEX_PATH=root / "scenes.index", SCENE_METADATA_PATH=root / "metadata.pkl", SCENE_REPORT_PATH=root / "report.json"), patch("core.onnx_models.OnnxEncoder", Encoder), patch.object(module, "resolve_model_path", return_value="test-model"):
                first = module.build_scene_index("test-model", source, recover_catalog=False)
                second = module.build_scene_index("test-model", source, recover_catalog=False)
                rows[0]["scene_timeline"][0]["visual_caption"] = "A red room"
                source.write_text(json.dumps(rows), encoding="utf-8")
                third = module.build_scene_index("test-model", source, recover_catalog=False)
            self.assertEqual(first["encoded_scene_vectors"], 2)
            self.assertEqual(second["reused_scene_vectors"], 2)
            self.assertEqual(third["reused_scene_vectors"], 1)
            self.assertEqual([len(batch) for batch in batches], [2, 1])
