import unittest
import weakref
from unittest.mock import patch

import numpy as np

from core.onnx_models import OnnxEncoder


class PooledEmbeddingMemoryTests(unittest.TestCase):
    def encoder(self, pooling="cls"):
        encoder = OnnxEncoder.__new__(OnnxEncoder)
        encoder.pooling = pooling
        encoder.config = {"hidden_size": 4}
        return encoder

    def test_cls_batches_do_not_retain_all_token_tensors(self):
        encoder = self.encoder()
        references, live_before_batch = [], []

        def forward(texts):
            live_before_batch.append(sum(ref() is not None for ref in references))
            hidden = np.ones((len(texts), 128, 4), dtype="float32")
            references.append(weakref.ref(hidden))
            return hidden, np.ones((len(texts), 128), dtype="int64")

        encoder.forward = forward
        result = encoder.encode(["sample"] * 12, batch_size=1)
        self.assertEqual(result.shape, (12, 4))
        self.assertLessEqual(max(live_before_batch), 1)
        np.testing.assert_allclose(result, .5)

    def test_normalization_does_not_mutate_the_token_tensor(self):
        encoder = self.encoder()
        hidden = np.arange(1, 25, dtype="float32").reshape(1, 6, 4)
        original = hidden.copy()
        encoder.forward = lambda texts: (hidden, np.ones((1, 6), dtype="int64"))
        result = encoder.encode("sample")
        np.testing.assert_array_equal(hidden, original)
        np.testing.assert_allclose(result, original[0, 0] / np.linalg.norm(original[0, 0]))

    def test_mean_pooling_still_respects_the_padding_mask(self):
        encoder = self.encoder("mean")
        encoder.forward = lambda texts: (np.array([[[1, 2, 3, 4], [9, 9, 9, 9]]], dtype="float32"),
                                          np.array([[1, 0]], dtype="int64"))
        np.testing.assert_array_equal(encoder.encode("sample", normalize_embeddings=False), [1, 2, 3, 4])

    def test_long_build_rechecks_headroom_before_the_next_batch(self):
        from core.resource_budget import ResourceBudgetError
        encoder = self.encoder()
        seen = []

        def forward(texts):
            seen.append(texts)
            return np.ones((1, 2, 4), dtype="float32"), np.ones((1, 2), dtype="int64")

        encoder.forward = forward
        with patch("core.resource_budget.check_model_budget", side_effect=[None, ResourceBudgetError("low disk")]) as budget:
            with self.assertRaisesRegex(ResourceBudgetError, "low disk"):
                encoder.encode(["sample"] * 130, batch_size=1)
        self.assertEqual(len(seen), 64)
        self.assertEqual(budget.call_count, 2)


if __name__ == "__main__":
    unittest.main()
