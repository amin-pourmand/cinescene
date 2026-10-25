import json
import base64
import struct
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BrandAssetTests(unittest.TestCase):
    def test_logo_sources_are_valid_and_identical_in_both_apps(self):
        for name in ("brand-mark.svg", "icon.svg"):
            local = (ROOT / "frontend/assets" / name).read_bytes()
            self.assertEqual(local, (ROOT / "docs/assets" / name).read_bytes())
            self.assertEqual(ET.fromstring(local).tag, "{http://www.w3.org/2000/svg}svg")

    def test_supplied_artwork_is_preserved_in_compatibility_icons(self):
        original = (ROOT / "frontend/assets/brand-symbol.jpg").read_bytes()
        for name in ("brand-mark.svg", "icon.svg"):
            root = ET.fromstring((ROOT / "frontend/assets" / name).read_bytes())
            image = root.find("{http://www.w3.org/2000/svg}image")
            self.assertEqual(base64.b64decode(image.attrib["href"].split(",", 1)[1]), original)
        for name in ("brand-symbol.jpg", "brand-lockup.jpg"):
            self.assertEqual((ROOT / "frontend/assets" / name).read_bytes(), (ROOT / "docs/assets" / name).read_bytes())

    def test_png_export_sizes_and_identical_app_assets(self):
        for name, size in (("icon-192.png", 192), ("icon-512.png", 512), ("icon-1024.png", 1024),
                           ("icon-maskable-512.png", 512), ("apple-touch-icon.png", 180),
                           ("favicon-32.png", 32), ("brand-mark-512.png", 512)):
            image = (ROOT / "frontend/assets" / name).read_bytes()
            self.assertEqual(image[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(struct.unpack(">II", image[16:24]), (size, size))
            self.assertEqual(image, (ROOT / "docs/assets" / name).read_bytes())

    def test_pwa_declares_dedicated_normal_and_maskable_icons(self):
        manifest = json.loads((ROOT / "docs/manifest.webmanifest").read_text(encoding="utf-8"))
        pngs = [icon for icon in manifest["icons"] if icon["type"] == "image/png"]
        self.assertTrue(any(icon["sizes"] == "192x192" and icon["purpose"] == "any" for icon in pngs))
        self.assertTrue(any(icon["sizes"] == "512x512" and icon["purpose"] == "any" for icon in pngs))
        self.assertTrue(any(icon["sizes"] == "512x512" and icon["purpose"] == "maskable" for icon in pngs))
        for icon in manifest["icons"]:
            self.assertTrue((ROOT / "docs" / icon["src"]).is_file())


if __name__ == "__main__":
    unittest.main()
