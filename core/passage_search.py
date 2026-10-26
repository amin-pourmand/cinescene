"""Experimental E5-small ablation; not the production retrieval engine."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import numpy as np

from core.onnx_models import OnnxEncoder, OnnxReranker, model_folder
from core.public_retrieval import catalog_passages, relevance_text, fuse_verification
from query_processor import QueryProcessor


ROOT = Path(__file__).resolve().parents[1]


class PassageSearchEngine:
    def __init__(self, enable_reranker=True, directory=None, include_private=True):
        directory = Path(directory or ROOT / "data/index/passage_experiment")
        catalog_bytes = (directory / "catalog.sample.json").read_bytes()
        self.manifest = json.loads((directory / "semantic-index.json").read_text(encoding="utf-8"))
        if hashlib.sha256(catalog_bytes).hexdigest() != self.manifest["catalog_sha256"]:
            raise ValueError("Catalog and semantic index differ. Rebuild scripts/build_public_semantic_index.py.")
        self.metadata = json.loads(catalog_bytes)["items"]
        self.passages = self.manifest["passages"]
        dimension = self.manifest["dimension"]
        self.vectors = np.fromfile(directory / "semantic-vectors.f32", dtype="<f4").reshape(-1, dimension)
        if len(self.vectors) != len(self.passages) or not np.isfinite(self.vectors).all():
            raise ValueError("Invalid semantic vectors.")
        self.model_path = self.manifest["model"]
        installed = json.loads((model_folder(self.model_path) / "artifact_manifest.json").read_text(encoding="utf-8"))
        if installed["revision"] != self.manifest["revision"]:
            raise ValueError("The installed encoder revision differs from the index. Prepare the pinned ONNX models again.")
        self.model = OnnxEncoder(self.model_path, self.manifest["max_length"])
        self.query_processor = QueryProcessor()
        if include_private:
            self._load_local_media()
        self.cross_encoder = OnnxReranker("Xenova/ms-marco-MiniLM-L-6-v2", 384) if enable_reranker else None

    def _load_local_media(self):
        path = ROOT / "data/processed/offline_media_enriched.json"
        if not path.exists():
            return
        positions = {str(item["id"]): i for i, item in enumerate(self.metadata)}
        local = json.loads(path.read_text(encoding="utf-8"))
        if not local:
            return
        for item in local:
            item["year"] = item.get("year") or item.get("release_year")
            item["mood"] = item.get("mood_tags", [])
            item["scenes"] = item.get("scene_descriptions", [])
            item["rating"] = item.get("rating") or item.get("vote_average") or 0
        replaced = {positions[str(item["id"])] for item in local if str(item["id"]) in positions}
        keep = [i for i, row in enumerate(self.passages) if row["item"] not in replaced]
        self.passages = [self.passages[i] for i in keep]
        self.vectors = self.vectors[keep]
        local_positions = []
        for item in local:
            position = positions.get(str(item["id"]))
            if position is None:
                position = len(self.metadata)
                self.metadata.append(item)
            else:
                self.metadata[position] = item
            local_positions.append(position)
        rows = catalog_passages(local)
        identity = json.dumps({"model": self.manifest["revision"], "length": self.manifest["max_length"], "rows": rows}, sort_keys=True).encode()
        digest = hashlib.sha256(identity).hexdigest()
        cache = ROOT / "data/index" / f"local-passages-{digest}.npy"
        if cache.exists():
            vectors = np.load(cache, allow_pickle=False)
        else:
            vectors = self.model.encode(["passage: " + row["text"] for row in rows], batch_size=4)
            cache.parent.mkdir(parents=True, exist_ok=True)
            np.save(cache, vectors, allow_pickle=False)
        self.passages.extend({**row, "item": local_positions[row["item"]]} for row in rows)
        self.vectors = np.concatenate([self.vectors, vectors])

    def search(self, query, top_k=10, use_reranking=True, media_type="all", scope="all", **kwargs):
        if scope not in {"all", "scenes", "catalog"}:
            raise ValueError("Unknown search scope")
        query = self.query_processor.normalize_unicode(query.strip())
        filters = self.query_processor.extract_filters(query)
        vector = self.model.encode("query: " + query)
        scores = self.vectors @ vector
        best = {}
        for row in np.argsort(scores)[::-1]:
            passage = self.passages[int(row)]
            index = passage["item"]
            if index in best:
                continue
            item = self.metadata[index]
            if scope == "scenes" and passage["kind"] != "scene":
                continue
            if scope == "catalog" and passage["kind"] == "scene":
                continue
            if media_type != "all" and item.get("media_type", "movie") != media_type:
                continue
            genres = set(item.get("genres", []))
            if filters["genres"] and not genres.intersection(filters["genres"]):
                continue
            if genres.intersection(filters["excluded_genres"]):
                continue
            if filters["year_range"]:
                year = str(item.get("year") or "")
                if not year.isdigit() or not filters["year_range"][0] <= int(year) <= filters["year_range"][1]:
                    continue
            if filters["director"] and filters["director"].casefold() not in str(item.get("director", "")).casefold():
                continue
            best[index] = {"item": index, "row": int(row), "score": float(scores[row])}
            if len(best) >= 100:
                break
        candidates = list(best.values())
        english = not re.search(r"[\u0600-\u06ff\u0400-\u04ff\u4e00-\u9fff]", query)
        if use_reranking and self.cross_encoder and english and candidates:
            pairs = []
            for candidate in candidates:
                item = self.metadata[candidate["item"]]
                evidence = self.passages[candidate["row"]]["text"]
                pairs.append([query, relevance_text(item, evidence)])
            values = self.cross_encoder.predict(pairs, batch_size=1)
            for candidate, value in zip(candidates, values):
                candidate["score"] = float(value)
            candidates.sort(key=lambda candidate: candidate["score"], reverse=True)
        output = []
        for rank, candidate in enumerate(candidates[:top_k], 1):
            item = self.metadata[candidate["item"]]
            passage = self.passages[candidate["row"]]
            scene = item.get("scene_timeline", [])[passage["scene"]] if passage["scene"] is not None else None
            output.append({**item, "rank": rank, "score": round(candidate["score"], 4),
                           "matched_scene": scene, "matched_scenes": [scene] if scene else [],
                           "evidence": passage["text"], "evidence_kind": passage["kind"], "ranking_method": candidate.get("method", "cross-encoder" if use_reranking and english else "cosine")})
        return output

    def status(self):
        scenes = sum(row["kind"] == "scene" for row in self.passages)
        return {"movies": len(self.metadata), "movie_vectors": len(self.metadata), "scene_vectors": scenes,
                "index_vectors": len(self.passages), "model": self.model_path, "embedding_dimension": self.manifest["dimension"],
                "device": "cpu", "precision": "int8", "runtime": "onnx", "reranker": bool(self.cross_encoder),
                "multilingual": True, "multilingual_model": self.model_path, "multilingual_vectors": len(self.passages),
                "fusion_version": "passage-grounded-ensemble-q8-v4",
                "index_path": "docs/data/semantic-vectors.f32"}
