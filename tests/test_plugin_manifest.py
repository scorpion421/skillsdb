"""
Unit tests for SkillsDB plugin manifest and assets.
Validates plugin structure, metadata, and branding assets.
"""

import json
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET


class TestPluginManifest(unittest.TestCase):
    def setUp(self):
        self.project_root = Path(__file__).resolve().parent.parent
        self.plugin_dir = self.project_root / "plugin"

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


if __name__ == "__main__":
    unittest.main()
