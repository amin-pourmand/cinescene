"""Reject stale, corrupt or privacy-unsafe public hybrid search artifacts."""
import hashlib
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def validate(directory=None):
    directory = Path(directory or ROOT / "docs/data")
    catalog = (directory / "catalog.sample.json").read_bytes()
    manifest = json.loads((directory / "hybrid-index.json").read_text(encoding="utf-8"))
    items = json.loads(catalog)["items"]
    if hashlib.sha256(catalog).hexdigest() != manifest["catalog_sha256"]:
        raise ValueError("Public catalog changed: rebuild its hybrid index before publishing.")
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
    return {"catalog_titles": len(items), "searchable_titles": titles, "records": len(records),
            "episode_records": sum(row["kind"] == "episode" for row in records),
            "scene_records": manifest["scene_records"], "multilingual_passages": len(mapping)}


if __name__ == "__main__":
    print(json.dumps(validate(), indent=2))
