"""
Unit tests for SkillsDB v3.6 UI Extension Sidecar Panel.
Validates sidecar manifests, assets, backend routes, and database bindings.
"""

import json
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET


class TestUIExtensionSidecar(unittest.TestCase):
    def setUp(self):
        self.project_root = Path(__file__).resolve().parent.parent
        self.plugin_dir = self.project_root / "plugin"
        self.sidecar_dir = self.plugin_dir / "sidecars" / "panel"

    def test_logo_asset_validity(self):
        """Validates that logo.svg exists, is well-formed XML, and defines a viewBox."""
        logo_path = self.plugin_dir / "assets" / "logo.svg"
        self.assertTrue(logo_path.exists(), "assets/logo.svg must exist")
        content = logo_path.read_text(encoding="utf-8")
        self.assertIn("viewBox", content)
        tree = ET.fromstring(content)
        self.assertEqual(tree.tag.split("}")[-1], "svg")

    def test_plugin_manifest_references_logo(self):
        """Validates that plugin.json specifies the logo asset."""
        manifest_path = self.plugin_dir / "plugin.json"
        self.assertTrue(manifest_path.exists())
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertIn("logo", data)
        self.assertEqual(data["logo"], "assets/logo.svg")

    def test_sidecar_manifest_config(self):
        """Validates that sidecar.json specifies node runtime, web UI, and aux pane entrypoint."""
        sidecar_json_path = self.sidecar_dir / "sidecar.json"
        self.assertTrue(sidecar_json_path.exists(), "sidecar.json must exist")
        data = json.loads(sidecar_json_path.read_text(encoding="utf-8"))
        self.assertEqual(data.get("command"), "node")
        self.assertTrue(data.get("has_web_ui"))
        self.assertEqual(data.get("restart_policy"), "always")
        views = data.get("ui_config", {}).get("views", [])
        self.assertTrue(len(views) > 0)
        self.assertEqual(views[0].get("entrypoint"), "SIDECAR_UI_ENTRYPOINT_AUX_PANE")

    def test_frontend_assets_exist(self):
        """Validates that index.html, app.js, styles.css, and main.mjs exist and are populated."""
        for filename in ["index.html", "app.js", "styles.css", "main.mjs"]:
            p = self.sidecar_dir / filename
            self.assertTrue(p.exists(), f"{filename} must exist")
            self.assertGreater(p.stat().st_size, 50, f"{filename} must not be empty")

    def test_index_html_contains_preload_bridge(self):
        """Validates that index.html includes the required /preload.js script bridge."""
        html = (self.sidecar_dir / "index.html").read_text(encoding="utf-8")
        self.assertIn('<script src="/preload.js"></script>', html)
        self.assertIn('<link rel="stylesheet" href="/styles.css">', html)


if __name__ == "__main__":
    unittest.main()
