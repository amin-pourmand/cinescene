"""Reject stale, corrupt or privacy-unsafe public hybrid search artifacts."""
import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def validate(directory=None):
    directory = Path(directory or ROOT / "docs/data")
    catalog = (directory / "catalog.sample.json").read_bytes()
    manifest = json.loads((directory / "hybrid-index.json").read_text(encoding="utf-8"))
    if manifest.get("version") != 3 or manifest.get("ranking_policy") != "independent-evidence-v1":
        raise ValueError("Public search needs the current independent-evidence policy")
    items = json.loads(catalog)["items"]
    if hashlib.sha256(catalog).hexdigest() != manifest["catalog_sha256"]:
        raise ValueError("Public catalog changed: rebuild its hybrid index before publishing.")
    summary_bytes = (directory / "catalog-summary.json").read_bytes()
    summary = json.loads(summary_bytes)["items"]
    release = json.loads((directory / "release.json").read_text(encoding="utf-8"))
    if release.get("catalog_sha256") != manifest["catalog_sha256"] or release.get("summary_sha256") != hashlib.sha256(summary_bytes).hexdigest():
        raise ValueError("The lightweight catalog and full search release differ")
    if release.get("index_generation") != manifest.get("index_generation"):
        raise ValueError("The visible release and active search generation differ")
    if len(summary) != len(items) or {str(row["id"]) for row in summary} != {str(row["id"]) for row in items}:
        raise ValueError("The lightweight catalog lost titles")
    private_path = ROOT / "data/processed/offline_media_enriched.json"
    if private_path.exists():
        from scripts.build_pwa_catalog import can_publish_media
        private_ids = {str(row["id"]) for row in json.loads(private_path.read_text(encoding="utf-8")) if not can_publish_media(row)}
        if private_ids & {str(row["id"]) for row in items}:
            raise ValueError("Public catalog contains a non-allowlisted private upload")
    for name, info in manifest["files"].items():
        if Path(name).name != name:
            raise ValueError("Invalid artifact path")
        data = (directory / name).read_bytes()
        if len(data) != info["bytes"] or hashlib.sha256(data).hexdigest() != info["sha256"]:
            raise ValueError(f"Public artifact failed checksum validation: {name}")
    records = manifest["records"]
    if manifest["files"]["hybrid-en.f32"]["bytes"] != len(records) * manifest["english"]["dimension"] * 4:
        raise ValueError("Invalid English vector dimensions")
    mapping = manifest["multilingual"]["records"]
    if manifest["files"]["hybrid-multilingual.f32"]["bytes"] != len(mapping) * manifest["multilingual"]["dimension"] * 4:
        raise ValueError("Invalid multilingual vector dimensions")
    if any(not 0 <= i < len(records) for i in mapping):
        raise ValueError("Invalid multilingual record mapping")
    texts = manifest["multilingual"].get("texts")
    if texts is not None and (len(texts) != len(mapping) or any(not isinstance(text, str) for text in texts)):
        raise ValueError("Invalid multilingual evidence mapping")
    count = manifest["lexical"]["postings"]
    binary = (directory / "hybrid-lexical.bin").read_bytes()
    if len(binary) != count * 8:
        raise ValueError("Invalid lexical dimensions")
    for (record_id,) in struct.iter_unpack("<I", binary[:count * 4]):
        if record_id >= len(records):
            raise ValueError("Lexical posting references a missing record")
    for posting in manifest["lexical"]["terms"].values():
        start, size = posting[:2]
        if start < 0 or size < 0 or start + size > count:
            raise ValueError("Invalid lexical posting range")
    for item in items:
        if item.get("source_video"):
            raise ValueError("Public catalog contains a local source path")
    for record in records:
        if not 0 <= record["item"] < len(items):
            raise ValueError("A search record references a missing title")
        item = items[record["item"]]
        if record["kind"] == "scene":
            if record["scene"] is None or not 0 <= record["scene"] < len(item.get("scene_timeline", [])):
                raise ValueError("Invalid extracted scene reference")
        elif record["scene"] is not None:
            raise ValueError("Story evidence was mislabeled as an extracted scene")
        if record.get("episode") is not None and not 0 <= record["episode"] < len(item.get("episodes", [])):
            raise ValueError("Invalid episode evidence reference")
    titles = len({record["item"] for record in records})
    if titles != manifest["titles"]:
        raise ValueError("Indexed title counts differ")
    if release.get("titles") != titles or release.get("episode_records") != sum(row["kind"] == "episode" for row in records):
        raise ValueError("The visible release has stale coverage counts")
    return {"catalog_titles": len(items), "searchable_titles": titles, "records": len(records),
            "episode_records": sum(row["kind"] == "episode" for row in records),
            "scene_records": manifest["scene_records"], "multilingual_passages": len(mapping)}


if __name__ == "__main__":
    print(json.dumps(validate(), indent=2))
