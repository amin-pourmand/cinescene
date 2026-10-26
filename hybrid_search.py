"""
CineScene hybrid retrieval engine.

Combines semantic FAISS retrieval, lightweight lexical retrieval, reciprocal
rank fusion, optional cross-encoder reranking, and query-time filters.
"""

from __future__ import annotations

from runtime_environment import configure_runtime

configure_runtime()

import os
import pickle
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import faiss
import numpy as np
from query_processor import QueryProcessor
from core.onnx_models import LazyOnnxEncoder, OnnxReranker, available as onnx_available

try:
    from rank_bm25 import BM25Okapi
except Exception:  # pragma: no cover - dependency fallback
    BM25Okapi = None

LOCAL_BGE_PATH = Path("models/bge-large-en-v1.5")
LEXICAL_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "while", "then", "they",
    "their", "there", "about", "after", "before", "are", "was", "were", "who", "his", "her",
    "she", "him", "its", "has", "have", "had", "but", "when", "where", "what", "which",
    "them", "can", "will", "how", "does", "did", "through",
    "این", "اون", "آن", "یک", "یکی", "برای", "های", "هایی", "است", "هست", "بود", "بوده",
    "شد", "شده", "شود", "شوند", "کند", "کنند", "کرد", "کرده", "دارد", "داره", "باشه",
    "باید", "همه", "خود", "خودش", "فیلم", "سریال", "سکانس", "صحنه",
}


def clean_text(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none"}:
        return ""
    return text


def resolve_existing(paths: List[str]) -> Optional[str]:
    for path in paths:
        if Path(path).exists():
            return path
    return None


def resolve_model_path(model_path: str, use_base_model: bool = False) -> str:
    if use_base_model:
        if (LOCAL_BGE_PATH / "config.json").exists():
            return str(LOCAL_BGE_PATH)
        return "BAAI/bge-large-en-v1.5"
    if Path(model_path).exists():
        return model_path
    if (LOCAL_BGE_PATH / "config.json").exists():
        return str(LOCAL_BGE_PATH)
    return model_path


def resolve_model_from_index_report(default_model_path: str, index_path: Optional[str]) -> str:
    if not index_path:
        return default_model_path
    report_path = Path(index_path).parent / "index_report.json"
    if not report_path.exists():
        return default_model_path
    try:
        with open(report_path, "r", encoding="utf-8") as f:
            report = json.load(f)
        model = report.get("model")
        if model and Path(model).exists():
            return model
    except Exception:
        return default_model_path
    return default_model_path


class HybridSearchEngine:
    def __init__(
        self,
        model_path: str = "models/cinescene-v2/final",
        index_path: str = "data/index/faiss_index_v2.bin",
        metadata_path: str = "data/index/metadata_v2.pkl",
        use_base_model: bool = False,
        cross_encoder_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        enable_reranker: bool = True,
    ):
        self.index_path = resolve_existing([index_path, "data/index/movies.index"])
        self.metadata_path = resolve_existing([metadata_path, "data/index/metadata.pkl"])
        reported_model = resolve_model_from_index_report(model_path, self.index_path)
        self.model_path = resolve_model_path(reported_model, use_base_model=use_base_model)

        if not self.index_path or not self.metadata_path:
            raise FileNotFoundError(
                "FAISS index is missing. Run build_index_v2.py after generating or enriching movies."
            )

        print(f"Loading embedding model: {self.model_path}")
        self.runtime = os.getenv("CINESCENE_MODEL_RUNTIME", "onnx")
        if self.runtime == "onnx":
            if not onnx_available(self.model_path):
                raise FileNotFoundError("Quantized models are missing. Run scripts/prepare_onnx_models.py first.")
            self.device, self.precision = "cpu", "int8"
            self.model = LazyOnnxEncoder(self.model_path)
        else:
            import torch
            from sentence_transformers import SentenceTransformer

            self.device = os.getenv("CINESCENE_EMBEDDING_DEVICE") or ("cuda" if torch.cuda.is_available() else "cpu")
            use_fp16 = self.device == "cuda" and os.getenv("CINESCENE_EMBEDDING_FP16", "0") == "1"
            self.precision = "float16" if use_fp16 else "float32"
            self.model = SentenceTransformer(self.model_path, device=self.device)
            if use_fp16:
                self.model.half()
        self.model.max_seq_length = min(
            int(self.model.max_seq_length),
            max(64, int(os.getenv("CINESCENE_EMBEDDING_MAX_SEQ", "256"))),
        )
        print(f"Loading FAISS index: {self.index_path}")
        self.index = faiss.read_index(self.index_path)

        print(f"Loading metadata: {self.metadata_path}")
        with open(self.metadata_path, "rb") as f:
            self.movie_metadata = pickle.load(f)

        from scene_index import load_scene_index

        self.scene_index, self.scene_metadata = load_scene_index(expected_dimension=int(self.index.d))
        self.scene_offset = len(self.movie_metadata)
        self.metadata = self.movie_metadata + self.scene_metadata
        series_path = Path("data/processed/tv_series_enriched.json")
        if series_path.exists():
            series_rows = json.loads(series_path.read_text(encoding="utf-8"))
            years = {str(row["id"]): str(row["premiered"])[:4] for row in series_rows
                     if row.get("premiere_source") and re.match(r"^\d{4}-\d{2}-\d{2}$", str(row.get("premiered") or ""))}
            for row in self.metadata:
                year = years.get(str(row.get("parent_id") or row.get("id")))
                if year:
                    row["year"] = year
        self.parent_metadata = {
            str(item.get("id")): item
            for item in self.movie_metadata
            if item.get("id") is not None
        }

        self.multilingual = None
        self.multilingual_error = None
        if os.getenv("CINESCENE_ENABLE_MULTILINGUAL", "1") == "1":
            from multilingual_index import INDEX_PATH, METADATA_PATH, MultilingualSearch

            if INDEX_PATH.exists() and METADATA_PATH.exists():
                try:
                    self.multilingual = MultilingualSearch(self.metadata)
                except Exception as exc:
                    self.multilingual_error = str(exc)

        self.query_processor = QueryProcessor()
        self._build_lexical_index()

        self.cross_encoder = None
        if enable_reranker:
            try:
                print(f"Loading cross-encoder: {cross_encoder_name}")
                local_reranker = Path("models/ms-marco-MiniLM-L-6-v2")
                reference = str(local_reranker) if (local_reranker / "config.json").exists() else cross_encoder_name
                if self.runtime == "onnx":
                    self.cross_encoder = OnnxReranker(reference, max_length=384)
                else:
                    from sentence_transformers import CrossEncoder

                    self.cross_encoder = CrossEncoder(reference, device="cpu", max_length=384)
            except Exception as exc:
                print(f"Cross-encoder unavailable, continuing without reranking: {exc}")

        print(
            f"Hybrid search ready with {len({str(row.get('parent_id') or row.get('id')) for row in self.movie_metadata})} titles and "
            f"{len(self.scene_metadata)} scene vectors"
        )

    def _doc_for_meta(self, meta: Dict) -> str:
        timeline_text = []
        for scene in meta.get("scene_timeline", []) or []:
            if isinstance(scene, dict):
                timeline_text.extend(
                    [
                        clean_text(scene.get("visual_caption")),
                        clean_text(scene.get("transcript")),
                        " ".join(scene.get("visual_tags", []) or []),
                        " ".join(scene.get("mood_tags", []) or []),
                        " ".join(scene.get("keywords", []) or []),
                    ]
                )
        return " ".join(
            [
                clean_text(meta.get("title")),
                clean_text(meta.get("overview")),
                " ".join(meta.get("genres", []) or []),
                " ".join(meta.get("mood_tags", []) or []),
                " ".join(meta.get("keywords", []) or []),
                " ".join(meta.get("visual_tags", []) or []),
                " ".join(meta.get("scene_descriptions", []) or []),
                " ".join(timeline_text),
                clean_text(meta.get("director")),
                clean_text(meta.get("rich_text")),
                clean_text(meta.get("source_video")),
            ]
        )

    def _build_lexical_index(self):
        self.lexical_docs = [self._lexical_tokens(self._doc_for_meta(meta)) for meta in self.metadata]
        self.lexical_sets = [set(tokens) for tokens in self.lexical_docs]
        self.title_token_sets = [set(self._lexical_tokens(meta.get("title", ""))) for meta in self.metadata]
        self.transcript_token_sets = []
        for meta in self.metadata:
            scene = meta.get("matched_scene") or {}
            transcript = scene.get("transcript", "") if isinstance(scene, dict) else ""
            self.transcript_token_sets.append(set(self._lexical_tokens(transcript)))
        if BM25Okapi is not None:
            self.bm25 = BM25Okapi(self.lexical_docs)
        else:
            self.bm25 = None

    @staticmethod
    def _lexical_tokens(text: str) -> List[str]:
        normalized_text = QueryProcessor.normalize_unicode(clean_text(text)).lower()
        tokens = re.findall(r"[^\W_]+", normalized_text, flags=re.UNICODE)
        normalized = []
        for token in tokens:
            if token.isascii():
                if len(token) > 4 and token.endswith("ies"):
                    token = token[:-3] + "y"
                elif len(token) > 4 and token.endswith("es") and token[-3] in {"s", "x", "z"}:
                    token = token[:-2]
                elif len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
                    token = token[:-1]
            if len(token) > 2 and token not in LEXICAL_STOPWORDS:
                normalized.append(token)
        return normalized

    def vector_search(self, query: str, k: int = 50) -> List[Tuple[int, float]]:
        query_text = "Represent this sentence for searching relevant passages: " + query
        query_emb = self.model.encode(query_text, convert_to_numpy=True, normalize_embeddings=True).astype("float32")
        query_emb = query_emb.reshape(1, -1)
        movie_k = min(k, len(self.movie_metadata))
        distances, indices = self.index.search(query_emb, movie_k)
        results = [(int(idx), float(score)) for idx, score in zip(indices[0], distances[0]) if int(idx) >= 0]

        if self.scene_index is not None and self.scene_metadata:
            scene_k = min(max(k, 80), len(self.scene_metadata))
            scene_distances, scene_indices = self.scene_index.search(query_emb, scene_k)
            results.extend(
                (self.scene_offset + int(idx), float(score))
                for idx, score in zip(scene_indices[0], scene_distances[0])
                if int(idx) >= 0
            )
        return sorted(results, key=lambda item: item[1], reverse=True)

    def lexical_search(self, query: str, k: int = 50) -> List[Tuple[int, float]]:
        k = min(k, len(self.metadata))
        query_tokens = self._lexical_tokens(query)
        if self.bm25 is not None:
            scores = self.bm25.get_scores(query_tokens)
        else:
            token_set = set(query_tokens)
            scores = np.array([len(token_set & set(doc)) / max(1, len(token_set)) for doc in self.lexical_docs])
        top_indices = np.argsort(scores)[::-1][:k]
        return [(int(idx), float(scores[idx])) for idx in top_indices if scores[idx] > 0]

    def direct_overlap_search(self, query: str, k: int = 50) -> List[Tuple[int, float]]:
        terms = set(self._lexical_tokens(query))
        if not terms:
            return []
        scored = []
        for idx, meta in enumerate(self.metadata):
            doc_terms = self.lexical_sets[idx]
            overlap = len(terms & doc_terms)
            if overlap:
                transcript_terms = self.transcript_token_sets[idx]
                transcript_overlap = len(terms & transcript_terms)
                source_bonus = min(2, transcript_overlap) if meta.get("record_type") == "scene" else 0
                scored.append((idx, float(overlap + source_bonus)))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:k]

    def reciprocal_rank_fusion(
        self,
        vector_results: List[Tuple[int, float]],
        lexical_results: List[Tuple[int, float]],
        k: int = 60,
    ) -> List[Tuple[int, float]]:
        scores: Dict[int, float] = {}
        for rank, (idx, _) in enumerate(vector_results):
            scores[idx] = scores.get(idx, 0.0) + 1 / (k + rank + 1)
        seen = set()
        for rank, (idx, _) in enumerate(lexical_results):
            if idx in seen:
                continue
            seen.add(idx)
            scores[idx] = scores.get(idx, 0.0) + 1 / (k + rank + 1)
        return sorted(scores.items(), key=lambda item: item[1], reverse=True)

    def lexical_boost(self, query: str, results: List[Tuple[int, float]]) -> List[Tuple[int, float]]:
        query_terms = set(self._lexical_tokens(query))
        if not query_terms:
            return results

        is_persian = bool(re.search(r"[\u0600-\u06ff]", query))
        boosted = []
        for idx, score in results:
            meta = self.metadata[idx]
            doc_terms = self.lexical_sets[idx]
            title_terms = self.title_token_sets[idx]
            overlap = len(query_terms & doc_terms)
            title_overlap = len(query_terms & title_terms)
            source_boost = 0.0
            if meta.get("record_type") == "scene" and overlap >= 2:
                transcript_terms = self.transcript_token_sets[idx]
                transcript_overlap = len(query_terms & transcript_terms)
                coverage = transcript_overlap / len(query_terms)
                if transcript_overlap >= 2 and coverage >= 0.65:
                    source_boost = 0.018 * coverage
            title_boost = 0.008 * title_overlap / len(query_terms)
            # A few common Persian words in a long local transcript must not beat
            # cross-language evidence over the entire English-language catalog.
            overlap_boost = 0.0 if is_persian else 0.008 * overlap / len(query_terms)
            boosted.append((idx, score + overlap_boost + title_boost + source_boost))
        boosted.sort(key=lambda item: item[1], reverse=True)
        return boosted

    def apply_filters(self, results: List[Tuple[int, float]], filters: Dict) -> List[Tuple[int, float]]:
        filtered = []
        for idx, score in results:
            meta = self.metadata[idx]

            if filters.get("media_type") in {"movie", "series"} and meta.get("media_type", "movie") != filters["media_type"]:
                continue
            if filters.get("genres"):
                meta_genres = {genre.replace("Science-Fiction", "Science Fiction") for genre in meta.get("genres", []) or []}
                if not any(genre in meta_genres for genre in filters["genres"]):
                    continue
            if {genre.replace("Science-Fiction", "Science Fiction") for genre in meta.get("genres", []) or []} & set(filters.get("excluded_genres", [])):
                continue
            if filters.get("scope") == "scenes" and meta.get("record_type") != "scene":
                continue
            if filters.get("scope") == "catalog" and meta.get("record_type") == "scene":
                continue

            if filters.get("year_range"):
                try:
                    year = int(meta.get("year"))
                    start, end = filters["year_range"]
                    if not (start <= year <= end):
                        continue
                except Exception:
                    continue

            if filters.get("director"):
                if filters["director"].lower() not in clean_text(meta.get("director")).lower():
                    continue

            filtered.append((idx, score))
        return filtered

    def _format_result(self, idx: int, score: float, rank: int, matched_scenes: Optional[List[Dict]] = None) -> Dict:
        candidate = self.metadata[idx]
        parent_id = candidate.get("parent_id") or candidate.get("id")
        meta = self.parent_metadata.get(str(parent_id), candidate)
        scene_matches = matched_scenes or []
        timeline = meta.get("scene_timeline", []) or []
        if not timeline and scene_matches:
            timeline = scene_matches
        return {
            "rank": rank,
            "id": parent_id,
            "title": meta.get("title", "Unknown"),
            "media_type": meta.get("media_type", "movie"),
            "season": meta.get("season"),
            "episode": meta.get("episode"),
            "year": meta.get("year", "N/A"),
            "genres": meta.get("genres", []) or [],
            "director": meta.get("director", "Unknown"),
            "cast": meta.get("cast", []) or [],
            "overview": meta.get("overview", ""),
            "rating": meta.get("rating", meta.get("vote_average", 0.0)),
            "popularity": meta.get("popularity", 0.0),
            "scenes": meta.get("scene_descriptions", []) or [],
            "scene_timeline": timeline,
            "matched_scene": scene_matches[0] if scene_matches else None,
            "matched_scenes": scene_matches,
            "matched_episode": candidate.get("matched_episode"),
            "evidence": candidate.get("overview", "") if candidate.get("record_type") == "episode" else meta.get("overview", ""),
            "evidence_kind": "episode" if candidate.get("record_type") == "episode" else "story",
            "scene_count": meta.get("scene_count"),
            "first_keyframe": meta.get("first_keyframe"),
            "visual_tags": meta.get("visual_tags", []) or [],
            "mood": meta.get("mood_tags", []) or [],
            "keywords": meta.get("keywords", []) or [],
            "source": meta.get("source", ""),
            "source_video": meta.get("source_video", ""),
            "score": round(float(score), 4),
        }

    def _collapse_titles(self, results: List[Tuple[int, float]]) -> List[Tuple[int, float, List[Dict]]]:
        grouped: Dict[str, Dict] = {}
        for idx, score in results:
            meta = self.metadata[idx]
            parent_id = str(meta.get("parent_id") or meta.get("id") or f"row:{idx}")
            group = grouped.setdefault(parent_id, {"idx": idx, "score": score, "scenes": []})
            if score > group["score"]:
                group["idx"] = idx
                group["score"] = score
            scene = meta.get("matched_scene")
            if meta.get("record_type") == "scene" and isinstance(scene, dict):
                scene_with_score = dict(scene)
                scene_with_score["match_score"] = round(float(score), 4)
                group["scenes"].append(scene_with_score)

        collapsed = []
        for group in grouped.values():
            scenes = sorted(group["scenes"], key=lambda item: item.get("match_score", 0), reverse=True)
            # Max-pool evidence: a long film must not win merely by having more scenes.
            collapsed.append((group["idx"], float(group["score"]), scenes[:5]))
        return sorted(collapsed, key=lambda item: item[1], reverse=True)

    def rerank_titles(self, query: str, candidates, limit: int = 40):
        if self.cross_encoder is None or not candidates or re.search(r"[\u0600-\u06ff]", query):
            return candidates
        selected = candidates[:limit]
        pairs = []
        for idx, _, scenes in selected:
            meta = self.metadata[idx]
            scene = scenes[0] if scenes else meta.get("matched_scene") or {}
            text = f"{meta.get('title', '')}. {meta.get('overview', '')}"
            if scene:
                text += f" Scene: {scene.get('transcript', '')} {scene.get('visual_caption', '')}"
            pairs.append([query, text])
        scores = self.cross_encoder.predict(pairs, batch_size=16, show_progress_bar=False)
        reranked = [(idx, float(score), scenes) for (idx, _, scenes), score in zip(selected, scores)]
        # Unscored retrieval scores and relevance logits are different scales.
        return sorted(reranked, key=lambda item: item[1], reverse=True) + candidates[limit:]

    def search(self, query: str, top_k: int = 10, use_reranking: bool = True, mode: str = "hybrid", media_type: str = "all", scope: str = "all") -> List[Dict]:
        if mode not in {"hybrid", "semantic", "lexical", "multilingual"}:
            raise ValueError("Unknown retrieval mode")
        if scope not in {"all", "scenes", "catalog"}:
            raise ValueError("Unknown search scope")
        processed = self.query_processor.process(query)
        search_query = processed["expanded"]
        is_persian = bool(re.search(r"[\u0600-\u06ff]", processed["cleaned"]))
        concepts = " ".join(word for word in search_query.split() if word.isascii()) if is_persian else ""
        translated = is_persian and len(self._lexical_tokens(concepts)) >= 3
        filters = processed["filters"]
        filters["media_type"] = media_type
        filters["scope"] = scope

        if mode == "semantic":
            fused_results = self.vector_search(search_query, k=120)
        elif mode == "multilingual":
            if self.multilingual is None:
                raise RuntimeError("Build the multilingual index before using this mode.")
            fused_results = self.multilingual.search(processed["cleaned"], k=150)
        elif mode == "lexical":
            fused_results = self.lexical_search(search_query, k=120)
        else:
            multilingual_results = self.multilingual.search(processed["cleaned"], k=150) if self.multilingual else []
            vector_results = self.vector_search(concepts if translated else search_query, k=100) if not is_persian or translated else []
            lexical_results = self.lexical_search(concepts if translated else processed["cleaned"], k=100)
            if is_persian and multilingual_results and not translated:
                # Most catalog text is English; lexical ranks over a few Persian subtitle
                # tracks are not comparable to multilingual recall over the whole catalog.
                lexical_scores = self.reciprocal_rank_fusion([], lexical_results)
                fused_results = [(idx, score * 0.15) for idx, score in lexical_scores]
            else:
                fused_results = self.reciprocal_rank_fusion(vector_results, lexical_results)
            if multilingual_results:
                scores = dict(fused_results)
                for rank, (idx, _) in enumerate(multilingual_results, 1):
                    scores[idx] = scores.get(idx, 0) + 1 / (60 + rank)
                fused_results = sorted(scores.items(), key=lambda item: item[1], reverse=True)
            fused_results = self.lexical_boost(processed["cleaned"], fused_results)

        if filters.get("genres") or filters.get("excluded_genres") or filters.get("year_range") or filters.get("director") or media_type != "all" or scope != "all":
            fused_results = self.apply_filters(fused_results, filters)

        collapsed = self._collapse_titles(fused_results)
        if use_reranking:
            collapsed = self.rerank_titles(concepts if translated else processed["cleaned"], collapsed)
        return [
            self._format_result(idx, score, rank + 1, matched_scenes=scenes)
            for rank, (idx, score, scenes) in enumerate(collapsed[:top_k])
        ]

    def status(self) -> Dict:
        return {
            "movies": len({str(row.get("parent_id") or row.get("id")) for row in self.movie_metadata}),
            "episode_vectors": sum(row.get("record_type") == "episode" for row in self.movie_metadata),
            "scene_vectors": len(self.scene_metadata),
            "index_vectors": int(self.index.ntotal) + (int(self.scene_index.ntotal) if self.scene_index is not None else 0),
            "movie_vectors": int(self.index.ntotal),
            "model": self.model_path,
            "embedding_dimension": int(self.index.d),
            "device": self.device,
            "precision": self.precision,
            "runtime": self.runtime,
            "index_path": self.index_path,
            "metadata_path": self.metadata_path,
            "reranker": bool(self.cross_encoder),
            "multilingual": self.multilingual is not None,
            "multilingual_model": self.multilingual.model_path if self.multilingual else None,
            "multilingual_vectors": int(self.multilingual.index.ntotal) if self.multilingual else 0,
            "fusion_version": "rrf-v6-multilingual-relevance",
            "multilingual_error": self.multilingual_error,
            "lexical": "bm25" if self.bm25 is not None else "token_overlap",
        }


if __name__ == "__main__":
    engine = HybridSearchEngine(enable_reranker=False)
    for item in engine.search("dark lonely science fiction movie", top_k=5, use_reranking=False):
        print(f"{item['rank']}. {item['title']} ({item['year']}) - {item['score']}")
