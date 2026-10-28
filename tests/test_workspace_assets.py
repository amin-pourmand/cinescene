import json
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]


class Page(HTMLParser):
    def __init__(self, path):
        super().__init__()
        self.elements = []
        self.feed(path.read_text(encoding="utf-8"))

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


class WorkspaceAssetTests(unittest.TestCase):
    def test_shared_workspace_code_stays_identical(self):
        for name in ("workspace-ui.js", "workspace.css"):
            self.assertEqual((ROOT / "frontend/assets" / name).read_bytes(),
                             (ROOT / "docs/assets" / name).read_bytes(), name)

    def test_pages_have_unique_ids_and_load_shared_code_before_app(self):
        for folder in ("frontend", "docs"):
            with self.subTest(folder=folder):
                page = Page(ROOT / folder / "index.html")
                ids = [attrs["id"] for _, attrs in page.elements if "id" in attrs]
                self.assertEqual(len(ids), len(set(ids)), "Duplicate element IDs")
                scripts = [urlsplit(attrs["src"]).path.rsplit("/", 1)[-1]
                           for tag, attrs in page.elements if tag == "script" and "src" in attrs]
                self.assertLess(scripts.index("workspace-ui.js"), scripts.index("app.js"))

    def test_pwa_precaches_every_entrypoint_and_references_real_files(self):
        source = (ROOT / "docs/sw.js").read_text(encoding="utf-8")
        assets = json.loads(re.search(r"const ASSETS = (\[.*?\]);", source, re.S)[1])
        for asset in assets:
            path = urlsplit(asset).path
            self.assertTrue((ROOT / "docs" / path).exists(), asset)
        page = Page(ROOT / "docs/index.html")
        for tag, attrs in page.elements:
            asset = attrs.get("src") if tag in {"script", "img"} else attrs.get("href") if tag == "link" else None
            if asset and asset.startswith("./"):
                self.assertIn(asset, assets, f"Offline shell is missing {asset}")

    def test_interface_is_english_and_scene_input_supports_bidirectional_text(self):
        for folder in ("frontend", "docs"):
            page = Page(ROOT / folder / "index.html")
            self.assertIn(("html", {"lang": "en"}), page.elements)
            query = next(attrs for _, attrs in page.elements if attrs.get("id") == "queryInput")
            self.assertEqual(query["dir"], "auto")
            self.assertEqual(query["maxlength"], "1000")

    def test_native_translation_warning_is_accessible_and_hidden_until_needed(self):
        page = Page(ROOT / "frontend/index.html")
        warning = next(attrs for _, attrs in page.elements if attrs.get("id") == "searchWarning")
        self.assertEqual(warning["role"], "status")
        self.assertIn("hidden", warning)
        self.assertIn("search-warning", warning["class"].split())
