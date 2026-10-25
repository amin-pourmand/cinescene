"""Optional multilingual retrieval channel; title vectors survive scene refreshes."""

from __future__ import annotations

from runtime_environment import configure_runtime

configure_runtime()

import argparse
import gc
import json
import pickle
import re
from pathlib import Path

import faiss
import numpy as np
import torch
from sentence_transformers import SentenceTransformer


MODEL_PATH = Path("models/multilingual-e5-small")
INDEX_PATH = Path("data/index/multilingual.index")
METADATA_PATH = Path("data/index/multilingual_metadata.json")
REPORT_PATH = Path("data/index/multilingual_report.json")


def record_key(item):
    return f"{item.get('record_type', 'title')}:{item.get('id')}"


def retrieval_text(item):
    scene = item.get("matched_scene")
    if isinstance(scene, dict):
        content = " ".join([
            str(scene.get("transcript") or ""), str(scene.get("visual_caption") or ""),
            " ".join(scene.get("keywords", []) or []),
        ])
    else:
        content = str(item.get("overview") or "")
        descriptions = item.get("scene_descriptions", []) or []
        content += " " + " ".join(str(value) for value in descriptions[:4])[:1200]
    return f"passage: {item.get('title', '')}. {content.strip()}"


def title_passages(item):
    overview = str(item.get("overview") or "").strip()
    sentences = [overview] if overview else []
    for description in item.get("scene_descriptions", []) or []:
        text = str(description).strip()
        if text and text not in overview and text not in sentences:
            sentences.append(text)
    text = " ".join(sentences).strip()
    if not text:
        return [retrieval_text(item)]
    # Keep plot details beyond the model's context window searchable.
    chunks = []
    current = ""
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        words = sentence.split()
        for position in range(0, len(words), 100):
            part = " ".join(words[position:position + 100])
            if len(current) + len(part) > 750 and current:
                chunks.append(current)
                current = " ".join(current.split()[-20:])
            current = (current + " " + part).strip()
    if current:
        chunks.append(current)
    return [f"passage: {item.get('title', '')}. {chunk}" for chunk in chunks]


def build_multilingual_index(scene_only=False, batch_size=16, model_path=None):
    existing_report = json.loads(REPORT_PATH.read_text(encoding="utf-8")) if REPORT_PATH.exists() else {}
    if model_path is None:
        model_path = existing_report.get("model") or str(MODEL_PATH)
    model_path = Path(model_path)
    if not (model_path / "model.safetensors").is_file():
        raise FileNotFoundError(f"No model.safetensors found in {model_path}. Download the selected E5 model first.")
    with open("data/index/metadata_v2.pkl", "rb") as handle:
        titles = pickle.load(handle)
    with open("data/index/scene_metadata.pkl", "rb") as handle:
        scenes = pickle.load(handle)
    old_index = None
    old_keys = []
    if scene_only and INDEX_PATH.exists() and METADATA_PATH.exists():
        old_index = faiss.read_index(str(INDEX_PATH))
        old_keys = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    title_documents = [(record_key(item), text) for item in titles for text in title_passages(item)]
    title_keys = [key for key, _ in title_documents]
    same_model = bool(existing_report.get("model")) and Path(existing_report["model"]).resolve() == model_path.resolve()
    keep_titles = same_model and old_index is not None and old_keys[:len(title_keys)] == title_keys
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = SentenceTransformer(str(model_path), device=device)
    model.max_seq_length = 384
    scene_documents = [retrieval_text(item) for item in scenes]
    documents = scene_documents if keep_titles else [text for _, text in title_documents] + scene_documents
    embeddings = model.encode(documents, batch_size=batch_size,
                              normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=True).astype("float32") if documents else np.empty((0, int(model.get_sentence_embedding_dimension())), dtype="float32")
    if keep_titles:
        embeddings = np.concatenate([old_index.reconstruct_n(0, len(title_keys)), embeddings])
    index = faiss.IndexFlatIP(int(model.get_sentence_embedding_dimension()))
    index.add(embeddings)
    keys = title_keys + [record_key(item) for item in scenes]
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = INDEX_PATH.with_suffix(".tmp")
    faiss.write_index(index, str(temporary))
    temporary.replace(INDEX_PATH)
    METADATA_PATH.write_text(json.dumps(keys), encoding="utf-8")
    report = {"model": str(model_path), "dimension": int(index.d), "vectors": int(index.ntotal),
              "titles": len(titles), "title_vectors": len(title_keys), "scene_vectors": len(scenes), "device": device,
              "query_prefix": "query: ", "passage_prefix": "passage: ", "reused_title_vectors": keep_titles}
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    del model
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return report


class MultilingualSearch:
    def __init__(self, metadata):
        self.index = faiss.read_index(str(INDEX_PATH))
        keys = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
        if len(keys) != int(self.index.ntotal):
            raise ValueError("Multilingual index and metadata counts differ.")
        self.positions = {record_key(item): index for index, item in enumerate(metadata)}
        self.keys = keys
        # Small single-query inference stays on CPU so the 4 GB GPU is free for BGE/vision.
        report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        self.model_path = report["model"]
        self.model = SentenceTransformer(self.model_path, device="cpu")
        self.model.max_seq_length = 384

    def search(self, query, k=100):
        vector = self.model.encode("query: " + query, normalize_embeddings=True, convert_to_numpy=True).astype("float32").reshape(1, -1)
        scores, indices = self.index.search(vector, min(k * 4, self.index.ntotal))
        results = {}
        for score, i in zip(scores[0], indices[0]):
            if int(i) >= 0 and self.keys[int(i)] in self.positions:
                position = self.positions[self.keys[int(i)]]
                results[position] = max(results.get(position, -1), float(score))
        return sorted(results.items(), key=lambda item: item[1], reverse=True)[:k]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene-only", action="store_true")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--model", default=None)
    args = parser.parse_args()
    print(json.dumps(build_multilingual_index(args.scene_only, args.batch_size, args.model), indent=2))
