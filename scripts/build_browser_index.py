"""Export the validated hybrid engine to portable, privacy-filtered browser assets."""

from __future__ import annotations

import hashlib
import gc
import json
import sys
from array import array
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hybrid_search import HybridSearchEngine, LEXICAL_STOPWORDS
from core.onnx_models import model_folder
from multilingual_index import record_key
from rank_bm25 import BM25Okapi


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def model_info(reference, dimension, pooling, length, prefix):
    source = json.loads((model_folder(reference) / "artifact_manifest.json").read_text(encoding="utf-8"))
    return {"model": source["repository"], "revision": source["revision"], "dimension": dimension,
            "pooling": pooling, "max_length": length, "prefix": prefix}


def main():
    directory = ROOT / "docs/data"
    catalog_path = directory / "catalog.sample.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))["items"]
    positions = {str(item["id"]): i for i, item in enumerate(catalog)}
    engine = HybridSearchEngine(enable_reranker=False)
    selected, records = [], []
    for index, meta in enumerate(engine.metadata):
        parent = str(meta.get("parent_id") or meta.get("id"))
        if parent not in positions:
            continue
        item = positions[parent]
        scene_index = None
        scene = meta.get("matched_scene")
        if meta.get("record_type") == "scene":
            timeline = catalog[item].get("scene_timeline", [])
            scene_index = next((i for i, row in enumerate(timeline) if abs(float(row.get("start_sec") or 0) - float(scene.get("start_sec") or 0)) < .001), None)
            if scene_index is None:
                continue
        episode_index = None
        if meta.get("record_type") == "episode":
            episode_index = next((i for i, row in enumerate(catalog[item].get("episodes", [])) if str(row.get("id")) == str(meta.get("id"))), None)
            if episode_index is None:
                continue
        selected.append(index)
        records.append({"item": item, "scene": scene_index, "episode": episode_index,
                        "overview": meta.get("overview", ""),
                        "kind": "scene" if scene_index is not None else "episode" if episode_index is not None else "title",
                        "title_tokens": sorted(engine.title_token_sets[index]),
                        "transcript_tokens": sorted(engine.transcript_token_sets[index])})
    remap = {old: new for new, old in enumerate(selected)}
    with (directory / "hybrid-en.f32").open("wb") as output:
        for i in selected:
            vector = engine.index.reconstruct(i) if i < engine.scene_offset else engine.scene_index.reconstruct(i - engine.scene_offset)
            np.asarray(vector, dtype="<f4").tofile(output)
    public_keys = []
    multilingual_rows = []
    for i, key in enumerate(engine.multilingual.keys):
        old = engine.multilingual.positions.get(key)
        if old in remap:
            public_keys.append(remap[old])
            multilingual_rows.append(i)
    with (directory / "hybrid-multilingual.f32").open("wb") as output:
        for i in multilingual_rows:
            np.asarray(engine.multilingual.index.reconstruct(i), dtype="<f4").tofile(output)

    # Public-only IDF must be rebuilt, but retaining two complete lexical
    # indexes and duplicate dense matrices can exceed a modest host's RAM.
    engine.bm25 = None
    engine.lexical_docs = []
    engine.lexical_sets = []
    engine.title_token_sets = []
    engine.transcript_token_sets = []
    gc.collect()

    # Precompute BM25 contributions with the existing library, using public data only.
    lexical_docs = []
    shared_tokens = {}
    for index in selected:
        metadata = {**engine.metadata[index], "source_video": ""}
        if metadata.get("source") == "offline_video_ingestion":
            metadata["rich_text"] = ""
        lexical_docs.append([shared_tokens.setdefault(token, token) for token in engine._lexical_tokens(engine._doc_for_meta(metadata))])
    bm25 = BM25Okapi(lexical_docs)
    del lexical_docs, shared_tokens
    postings = defaultdict(lambda: (array("I"), array("f")))
    for index, frequencies in enumerate(bm25.doc_freqs):
        normalization = bm25.k1 * (1 - bm25.b + bm25.b * bm25.doc_len[index] / bm25.avgdl)
        for token, frequency in frequencies.items():
            contribution = bm25.idf[token] * frequency * (bm25.k1 + 1) / (frequency + normalization)
            postings[token][0].append(index)
            postings[token][1].append(contribution)
    vocabulary, ids, weights = {}, array("I"), array("f")
    for token in sorted(postings):
        row_ids, row_weights = postings.pop(token)
        vocabulary[token] = [len(ids), len(row_ids), bm25.idf[token]]
        ids.extend(row_ids)
        weights.extend(row_weights)
    del bm25, postings
    with (directory / "hybrid-lexical.bin").open("wb") as output:
        np.asarray(ids, dtype="<u4").tofile(output)
        np.asarray(weights, dtype="<f4").tofile(output)
    files = {name: {"bytes": (directory / name).stat().st_size, "sha256": digest(directory / name)}
             for name in ("hybrid-en.f32", "hybrid-multilingual.f32", "hybrid-lexical.bin")}
    payload = {"version": 3, "catalog_sha256": digest(catalog_path), "files": files, "records": records,
               "english": model_info("Xenova/bge-large-en-v1.5", 1024, "cls", 256, "Represent this sentence for searching relevant passages: "),
               "multilingual": {**model_info("Xenova/multilingual-e5-base", 768, "mean", 384, "query: "), "records": public_keys,
                                "texts": [engine.multilingual.passages[i].removeprefix("passage: ") for i in multilingual_rows]},
               "reranker": model_info("Xenova/ms-marco-MiniLM-L-6-v2", 1, "", 384, ""),
               "translation": {"model": "Xenova/nllb-200-distilled-600M", "revision": "261c31d1a5732c67cdd16d80e8d6088507c7ccea",
                               "license": "CC-BY-NC-4.0", "download_bytes": 911957478,
                               "src_lang": "pes_Arab", "tgt_lang": "eng_Latn", "max_new_tokens": 320},
               "lexical": {"terms": vocabulary, "postings": len(ids)},
               "processor": {"stopwords": sorted(LEXICAL_STOPWORDS), "expansions": engine.query_processor.expansions,
                             "genre_aliases": engine.query_processor.genre_aliases},
               "titles": len({row["item"] for row in records}), "scene_records": sum(row["kind"] == "scene" for row in records),
               "fusion_version": engine.status()["fusion_version"], "index_generation": engine.status().get("index_generation"),
               "ranking_policy": "independent-evidence-v1", "private_media_exported": False}
    target = directory / "hybrid-index.json"
    target.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    summary_path = directory / "catalog-summary.json"
    release = {"version": 1, "titles": payload["titles"], "episode_records": sum(row["kind"] == "episode" for row in records),
               "scene_records": payload["scene_records"], "index_generation": payload["index_generation"],
               "fusion_version": payload["fusion_version"], "ranking_policy": payload["ranking_policy"],
               "catalog_sha256": payload["catalog_sha256"], "summary_sha256": digest(summary_path),
               "translation": payload["translation"]}
    (directory / "release.json").write_text(json.dumps(release, indent=2), encoding="utf-8")
    print(json.dumps({"titles": payload["titles"], "records": len(records), "multilingual_passages": len(public_keys),
                      "files": files, "manifest_bytes": target.stat().st_size}, indent=2))


if __name__ == "__main__":
    main()
