"""Bounded-memory ONNX inference compatible with the existing FAISS vectors."""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np


MODEL_ROOT = Path(__file__).resolve().parents[1] / "models/onnx"


def model_folder(reference: str) -> Path:
    return MODEL_ROOT / str(reference).replace("\\", "/").rstrip("/").split("/")[-1]


def available(reference: str) -> bool:
    folder = model_folder(reference)
    return (folder / "onnx/model_quantized.onnx").is_file() and (folder / "tokenizer.json").is_file()


class OnnxModel:
    def __init__(self, reference: str, max_length: int = 256):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        self.folder = model_folder(reference)
        self.tokenizer = Tokenizer.from_file(str(self.folder / "tokenizer.json"))
        self.config = json.loads((self.folder / "config.json").read_text(encoding="utf-8"))
        self.max_seq_length = max_length
        pad = next(((self.tokenizer.token_to_id(token), token) for token in ("<pad>", "[PAD]")
                    if self.tokenizer.token_to_id(token) is not None), (0, "[PAD]"))
        self.tokenizer.enable_padding(pad_id=pad[0], pad_token=pad[1])
        options = ort.SessionOptions()
        options.intra_op_num_threads = max(1, min(4, int(os.getenv("CINESCENE_CPU_THREADS", "2"))))
        options.inter_op_num_threads = 1
        # Variable-length requests should not retain a growing collection of arenas.
        options.enable_cpu_mem_arena = False
        options.enable_mem_pattern = False
        self.session = ort.InferenceSession(str(self.folder / "onnx/model_quantized.onnx"),
                                            sess_options=options, providers=["CPUExecutionProvider"])
        self.input_names = {item.name for item in self.session.get_inputs()}

    def forward(self, texts):
        self.tokenizer.enable_truncation(max_length=int(self.max_seq_length))
        encoded = self.tokenizer.encode_batch(texts)
        arrays = {
            "input_ids": np.asarray([item.ids for item in encoded], dtype=np.int64),
            "attention_mask": np.asarray([item.attention_mask for item in encoded], dtype=np.int64),
            "token_type_ids": np.asarray([item.type_ids for item in encoded], dtype=np.int64),
        }
        inputs = {name: arrays[name] for name in self.input_names}
        return self.session.run(None, inputs)[0], arrays["attention_mask"]


class OnnxEncoder(OnnxModel):
    def __init__(self, reference: str, max_length: int = 256):
        super().__init__(reference, max_length)
        self.pooling = "cls" if "bge-" in str(reference).lower() else "mean"

    def get_sentence_embedding_dimension(self):
        return int(self.config["hidden_size"])

    def encode(self, sentences, batch_size=8, normalize_embeddings=True, **kwargs):
        single = isinstance(sentences, str)
        rows = [sentences] if single else list(sentences)
        chunks = []
        for offset in range(0, len(rows), batch_size):
            hidden, mask = self.forward(rows[offset:offset + batch_size])
            if self.pooling == "cls":
                vectors = hidden[:, 0]
            else:
                weights = mask.astype(np.float32)[..., None]
                vectors = (hidden * weights).sum(axis=1) / np.maximum(weights.sum(axis=1), 1)
            vectors = np.asarray(vectors, dtype=np.float32)
            if normalize_embeddings:
                vectors /= np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-12)
            chunks.append(vectors)
        result = np.concatenate(chunks) if chunks else np.empty((0, self.get_sentence_embedding_dimension()), dtype=np.float32)
        return result[0] if single else result


class OnnxReranker(OnnxModel):
    def predict(self, pairs, batch_size=4, **kwargs):
        scores = []
        for offset in range(0, len(pairs), min(4, batch_size)):
            logits, _ = self.forward([tuple(pair) for pair in pairs[offset:offset + min(4, batch_size)]])
            scores.extend(np.asarray(logits).reshape(-1).tolist())
        return np.asarray(scores, dtype=np.float32)


class LazyOnnxEncoder:
    """Load one encoder at a time, then release its native buffers after encoding."""

    def __init__(self, reference, max_length=256):
        self.reference = reference
        self.max_seq_length = max_length
        self.config = json.loads((model_folder(reference) / "config.json").read_text(encoding="utf-8"))

    def get_sentence_embedding_dimension(self):
        return int(self.config["hidden_size"])

    def encode(self, sentences, **kwargs):
        model = OnnxEncoder(self.reference, self.max_seq_length)
        try:
            return model.encode(sentences, **kwargs)
        finally:
            del model
