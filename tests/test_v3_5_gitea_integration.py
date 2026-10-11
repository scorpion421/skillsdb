"""
Unit tests for SkillsDB v3.5 Gitea Integration & Snapshot Git Coupling.
"""

import os
import sys
import io
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from skillsdb.config import __version__
from skillsdb.platform.gitea import (
    get_gitea_config,
    check_gitea_connection,
    create_or_get_repo,
    is_git_repo,
    get_remote_url,
    init_gitea_workspace,
    sync_to_gitea,
    ensure_gitignore,
    find_gitea_executable,
    start_gitea_server,
)
from skillsdb.memory.project_memory import (
    init_project_db,
    mem_save_snapshot,
    mem_get_context,
)
from skillsdb.cli import main, build_parser


class TestGiteaIntegration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="test_skillsdb_gitea_"))

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_version_bump(self):
        self.assertEqual(__version__, "3.5.0")

    def test_gitea_config_defaults(self):
        cfg = get_gitea_config()
        self.assertTrue(cfg["url"].startswith("http"))
        self.assertIn("/api/v1", cfg["api_url"])
        self.assertEqual(cfg["bot_user"], "Antigravity")
        self.assertEqual(cfg["default_owner"], "MickyFoley")

    def test_check_gitea_connection_live(self):
        # Local Gitea is running at 127.0.0.1:3000
        res = check_gitea_connection(timeout=2.0)
        self.assertTrue(res.get("connected"), f"Expected connection to local Gitea: {res.get('error')}")
        self.assertEqual(res.get("username"), "Antigravity")
        self.assertTrue(res.get("is_admin"))

    def test_create_or_get_existing_repo(self):
        # We already created SkillsDB repository earlier
        res = create_or_get_repo("SkillsDB", owner="MickyFoley")
        self.assertIn(res.get("status"), ("exists", "created"))
        self.assertEqual(res.get("name"), "SkillsDB")
        self.assertEqual(res.get("owner"), "MickyFoley")

    def test_database_snapshot_git_commit_hash_column(self):
        db_path = self.temp_dir / "memory.db"
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        init_project_db(conn)

        cur = conn.cursor()
        cur.execute("PRAGMA table_info(session_snapshots);")
        cols = {row[1] for row in cur.fetchall()}
        self.assertIn("git_commit_hash", cols)
        conn.close()

    def test_mem_save_snapshot_with_git_sync(self):
        db_path = self.temp_dir / ".agents" / "memory.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        init_project_db(conn)

        # Mock sync_to_gitea
        with patch("skillsdb.memory.project_memory.is_git_repo", return_value=True), \
             patch("skillsdb.memory.project_memory.sync_to_gitea", return_value={
                 "status": "synced",
                 "committed": True,
                 "commit_hash": "a1b2c3d4e5f6",
                 "pushed": True,
             }):
            mem_save_snapshot(conn, "Feature complete", db_path=db_path, silent=True, git_sync=True)

        cur = conn.cursor()
        cur.execute("SELECT summary, git_commit_hash FROM session_snapshots ORDER BY id DESC LIMIT 1;")
        row = cur.fetchone()
        self.assertEqual(row["summary"], "Feature complete")
        self.assertEqual(row["git_commit_hash"], "a1b2c3d4e5f6")
        conn.close()

    def test_mem_get_context_outputs_commit_hash(self):
        db_path = self.temp_dir / ".agents" / "memory.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        init_project_db(conn)

        cur = conn.cursor()
        cur.execute("""
            INSERT INTO session_snapshots (conversation_id, summary, next_steps, git_commit_hash, created_at)
            VALUES ('test-cid', 'Milestone with Git', 'Deploy to staging', '9876543210ab', '2026-10-11T23:00:00Z');
        """)
        conn.commit()

        captured = io.StringIO()
        with patch("sys.stdout", captured):
            mem_get_context(conn, project_root=self.temp_dir)

        output = captured.getvalue()
        self.assertIn("Milestone with Git", output)
        self.assertIn("Git Commit: 98765432", output)
        conn.close()

    def test_cli_gitea_status_command(self):
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            main(["gitea", "status", "--project", str(self.temp_dir)])

        output = captured.getvalue()
        self.assertIn("GITEA LOCAL INTEGRATION STATUS", output)
        self.assertIn("Gitea Instance: [CONNECTED]", output)

    def test_ensure_gitignore_auto_generation(self):
        proj_dir = self.temp_dir / "my_project"
        proj_dir.mkdir(parents=True, exist_ok=True)
        gi_path = proj_dir / ".gitignore"
        self.assertFalse(gi_path.exists())

        created = ensure_gitignore(proj_dir)
        self.assertTrue(created)
        self.assertTrue(gi_path.exists())

        content = gi_path.read_text(encoding="utf-8")
        self.assertIn(".env", content)
        self.assertIn("node_modules/", content)
        self.assertIn("__pycache__/", content)
        self.assertIn(".agents/memory.db*", content)

        # Calling again should not overwrite
        created_again = ensure_gitignore(proj_dir)
        self.assertFalse(created_again)

    def test_find_gitea_executable(self):
        exe = find_gitea_executable()
        self.assertIsNotNone(exe)
        self.assertTrue(exe.is_file())
        self.assertIn("gitea", exe.name.lower())


if __name__ == "__main__":
    unittest.main()
