import io
import sys
import json
import shutil
import sqlite3
import unittest
import subprocess
from pathlib import Path

# Add database dir to path
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "database"))
import db_manager


class TestSkillsDBAutonomous(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_db_dir = REPO_ROOT / "tests" / "scratch"
        cls.test_db_dir.mkdir(parents=True, exist_ok=True)
        cls.test_db_path = cls.test_db_dir / "test_customizations.db"
        if cls.test_db_path.exists():
            cls.test_db_path.unlink()
        
        # Copy real database for testing
        real_db = REPO_ROOT / "database" / "customizations.db"
        if real_db.exists():
            shutil.copy2(real_db, cls.test_db_path)
            cls.conn = db_manager.get_connection(cls.test_db_path)
        else:
            cls.conn = db_manager.get_connection(cls.test_db_path)
            db_manager.init_db(cls.conn)

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        shutil.rmtree(cls.test_db_dir, ignore_errors=True)

    def test_extract_skill_sections(self):
        sample_md = """---
name: test-skill
description: Test skill description
---
# Test Skill Title

## Section One
Content of section one with details.

## Section Two
Content of section two with code:
```python
print("Hello World")
```
"""
        sections = db_manager.extract_skill_sections(sample_md)
        self.assertTrue(len(sections) >= 2)
        titles = [s["title"] for s in sections]
        self.assertIn("Section One", titles)
        self.assertIn("Section Two", titles)

    def test_get_skill_summary(self):
        buf = io.StringIO()
        orig_stdout = sys.stdout
        try:
            sys.stdout = buf
            db_manager.get_skill(self.conn, "flutter-fix-layout-issues", summary=True)
        finally:
            sys.stdout = orig_stdout
        out = buf.getvalue()
        self.assertIn("Micro-Skill Sections", out)
        self.assertIn("flutter-fix-layout-issues", out)

    def test_get_skill_section(self):
        buf = io.StringIO()
        orig_stdout = sys.stdout
        try:
            sys.stdout = buf
            db_manager.get_skill(self.conn, "flutter-fix-layout-issues", section="Constraint Violation Diagnostics")
        finally:
            sys.stdout = orig_stdout
        out = buf.getvalue()
        self.assertIn("Constraint Violation Diagnostics", out)
        self.assertIn("Vertical viewport was given unbounded height", out)

    def test_learn_rule(self):
        test_key = "test-auto-rule"
        test_name = "Automated Learning Test"
        test_content = "# Test Rule\nThis is a learned rule."
        
        db_manager.learn_rule(self.conn, test_key, test_name, test_content, category="testing")
        
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM rules WHERE key = ?", (test_key,))
        row = cur.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["name"], test_name)
        self.assertEqual(row["category"], "testing")

    def test_doctor_execution(self):
        buf = io.StringIO()
        orig_stdout = sys.stdout
        try:
            sys.stdout = buf
            db_manager.doctor(self.conn)
        finally:
            sys.stdout = orig_stdout
        out = buf.getvalue()
        self.assertIn("SKILLSDB SYSTEM DIAGNOSTICS", out)
        self.assertIn("[OK] Central Database", out)

    def test_pre_invocation_hook(self):
        # Create temporary project with memory.db
        test_proj = self.test_db_dir / "test_project"
        test_proj.mkdir(parents=True, exist_ok=True)
        pconn = db_manager.get_project_connection(test_proj)
        db_manager.mem_save_fact(pconn, "framework", "DirectML")
        db_manager.mem_save_decision(pconn, "Scaling", "Native D3D11 VP", category="architecture")
        db_manager.mem_save_snapshot(pconn, "Release v1.0 deployed successfully")
        pconn.close()

        # Run hook logic with mock payload
        mock_payload = json.dumps({
            "invocationNum": 1,
            "workspacePaths": [str(test_proj)]
        })
        
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "database" / "db_manager.py"), "mem-pre-invocation-hook"],
            input=mock_payload,
            capture_output=True,
            text=True
        )
        self.assertEqual(proc.returncode, 0)
        resp = json.loads(proc.stdout.strip())
        self.assertIn("injectSteps", resp)
        self.assertTrue(len(resp["injectSteps"]) > 0)
        msg = resp["injectSteps"][0]["ephemeralMessage"]
        self.assertIn("DirectML", msg)
        self.assertIn("Native D3D11 VP", msg)
        self.assertIn("Release v1.0 deployed", msg)


if __name__ == "__main__":
    unittest.main()
