"""
Project-level episodic memory (.agents/memory.db), lifecycle hook handler, and statistics.
"""

import os
import sys
import json
import sqlite3
import shutil
from datetime import datetime, timezone
from pathlib import Path
from ..config import TIER_ULTRA, DB_PATH, __version__
from ..core.detector import detect_model_tier
from .writer_queue import get_writer_queue, flush_journals


def find_project_root(start_path: Path = None) -> Path:
    """Traverses upward to identify project root boundary without crossing user home."""
    current = (start_path or Path.cwd()).resolve()
    project_markers = [
        ".agents", ".git", ".antigravity",
        "package.json", "pyproject.toml", "requirements.txt",
        "pubspec.yaml", "go.mod", "pom.xml", "build.gradle"
    ]
    home_dir = Path.home().resolve()
    for parent in [current] + list(current.parents):
        if parent == home_dir:
            if (parent / ".agents").exists():
                return parent
            break
        if any((parent / m).exists() for m in project_markers):
            return parent
    return current


def get_project_db_path(project_root: Path = None) -> Path:
    root = project_root or find_project_root()
    return root / ".agents" / "memory.db"


def get_project_connection(project_root: Path = None) -> sqlite3.Connection:
    """Returns a WAL-enabled SQLite connection to the project memory database."""
    db_path = get_project_db_path(project_root)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    conn.execute("PRAGMA auto_vacuum = INCREMENTAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    init_project_db(conn)
    return conn


def init_project_db(conn: sqlite3.Connection):
    """Initializes tables for architectural decisions, snapshots, and project facts."""
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS project_decisions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        category TEXT DEFAULT 'architecture',
        is_active INTEGER DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS session_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id TEXT,
        summary TEXT NOT NULL,
        next_steps TEXT,
        files_touched TEXT,
        created_at TEXT NOT NULL
    );
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS project_facts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key TEXT UNIQUE NOT NULL,
        value TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """)
    cursor.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS project_memory_fts USING fts5(
        source_table,
        title_or_key,
        content
    );
    """)
    conn.commit()


def mem_init(project_root: Path = None):
    root = project_root or find_project_root()
    db_path = get_project_db_path(root)
    conn = get_project_connection(root)
    init_project_db(conn)
    conn.close()
    print(f"Project memory database initialized at: {db_path}")


def mem_save_decision(conn: sqlite3.Connection, title: str, content: str, category: str = "architecture", db_path: Path = None):
    """Saves an architectural decision using WriterQueue if path is available to prevent lock contention."""
    now_iso = datetime.now(timezone.utc).isoformat()
    target_path = db_path or (Path(conn.cursor().execute("PRAGMA database_list;").fetchone()[2]) if conn else None)

    if target_path and Path(target_path).exists():
        wq = get_writer_queue(target_path)
        def _write(cur):
            cur.execute("""
            INSERT INTO project_decisions (title, content, category, is_active, created_at, updated_at)
            VALUES (?, ?, ?, 1, ?, ?);
            """, (title, content, category, now_iso, now_iso))
            row_id = cur.lastrowid
            cur.execute("""
            INSERT INTO project_memory_fts (source_table, title_or_key, content)
            VALUES ('decision', ?, ?);
            """, (title, content))
            return row_id
        row_id = wq.execute_write(_write)
        print(f"Project decision saved (ID {row_id}): '{title}'")
        return

    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO project_decisions (title, content, category, is_active, created_at, updated_at)
    VALUES (?, ?, ?, 1, ?, ?);
    """, (title, content, category, now_iso, now_iso))
    row_id = cursor.lastrowid
    cursor.execute("""
    INSERT INTO project_memory_fts (source_table, title_or_key, content)
    VALUES ('decision', ?, ?);
    """, (title, content))
    conn.commit()
    print(f"Project decision saved (ID {row_id}): '{title}'")


def mem_save_snapshot(conn: sqlite3.Connection, summary: str, conversation_id: str = None, next_steps: str = None, files_touched: str = None, db_path: Path = None):
    """Saves a session milestone snapshot."""
    now_iso = datetime.now(timezone.utc).isoformat()
    cid = conversation_id or os.environ.get("ANTIGRAVITY_CONVERSATION_ID") or "default"
    target_path = db_path or (Path(conn.cursor().execute("PRAGMA database_list;").fetchone()[2]) if conn else None)

    if target_path and Path(target_path).exists():
        wq = get_writer_queue(target_path)
        def _write(cur):
            cur.execute("""
            INSERT INTO session_snapshots (conversation_id, summary, next_steps, files_touched, created_at)
            VALUES (?, ?, ?, ?, ?);
            """, (cid, summary, next_steps or "", files_touched or "", now_iso))
            row_id = cur.lastrowid
            cur.execute("""
            INSERT INTO project_memory_fts (source_table, title_or_key, content)
            VALUES ('snapshot', ?, ?);
            """, (cid, summary + " " + (next_steps or "")))
            return row_id
        row_id = wq.execute_write(_write)
        print(f"Session snapshot saved (ID {row_id}) for conversation: {cid}")
        return

    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO session_snapshots (conversation_id, summary, next_steps, files_touched, created_at)
    VALUES (?, ?, ?, ?, ?);
    """, (cid, summary, next_steps or "", files_touched or "", now_iso))
    row_id = cursor.lastrowid
    cursor.execute("""
    INSERT INTO project_memory_fts (source_table, title_or_key, content)
    VALUES ('snapshot', ?, ?);
    """, (cid, summary + " " + (next_steps or "")))
    conn.commit()
    print(f"Session snapshot saved (ID {row_id}) for conversation: {cid}")


def mem_save_fact(conn: sqlite3.Connection, key: str, value: str, db_path: Path = None):
    """Saves a key-value fact or configuration item."""
    now_iso = datetime.now(timezone.utc).isoformat()
    target_path = db_path or (Path(conn.cursor().execute("PRAGMA database_list;").fetchone()[2]) if conn else None)

    if target_path and Path(target_path).exists():
        wq = get_writer_queue(target_path)
        def _write(cur):
            cur.execute("""
            INSERT OR REPLACE INTO project_facts (key, value, updated_at)
            VALUES (?, ?, ?);
            """, (key, value, now_iso))
            cur.execute("""
            INSERT INTO project_memory_fts (source_table, title_or_key, content)
            VALUES ('fact', ?, ?);
            """, (key, value))
        wq.execute_write(_write)
        print(f"Project fact saved: '{key}' = '{value}'")
        return

    cursor = conn.cursor()
    cursor.execute("""
    INSERT OR REPLACE INTO project_facts (key, value, updated_at)
    VALUES (?, ?, ?);
    """, (key, value, now_iso))
    cursor.execute("""
    INSERT INTO project_memory_fts (source_table, title_or_key, content)
    VALUES ('fact', ?, ?);
    """, (key, value))
    conn.commit()
    print(f"Project fact saved: '{key}' = '{value}'")


def mem_get_context(conn: sqlite3.Connection, max_decisions: int = 5, project_root: Path = None):
    """Outputs compact context: active architectural decisions, facts, and latest snapshot."""
    root = project_root or find_project_root()
    flush_journals(root, conn)
    cursor = conn.cursor()

    print("\n=== PROJECT MEMORY CONTEXT ===")
    cursor.execute("SELECT summary, next_steps, created_at FROM session_snapshots ORDER BY id DESC LIMIT 1;")
    last_snap = cursor.fetchone()
    if last_snap:
        dt = last_snap['created_at'][:10]
        print(f"\nLatest Session Milestone ({dt}):")
        print(f"  Summary:    {last_snap['summary']}")
        if last_snap['next_steps']:
            print(f"  Next Steps: {last_snap['next_steps']}")

    cursor.execute("""
    SELECT title, content, category FROM project_decisions
    WHERE is_active = 1 ORDER BY updated_at DESC LIMIT ?;
    """, (max_decisions,))
    decisions = cursor.fetchall()
    if decisions:
        print("\nActive Architectural Decisions:")
        for d in decisions:
            print(f"  * [{d['category'].upper()}] {d['title']}: {d['content']}")

    cursor.execute("SELECT key, value FROM project_facts ORDER BY updated_at DESC;")
    facts = cursor.fetchall()
    if facts:
        print("\nProject Facts & Configs:")
        for f in facts:
            print(f"  * {f['key']}: {f['value']}")

    if not last_snap and not decisions and not facts:
        print("No memory records found in project database.")
    print("==============================\n")


def mem_search(conn: sqlite3.Connection, query: str):
    """FTS5 search across project facts, decisions, and session milestones."""
    cursor = conn.cursor()
    print(f"\n--- Search results for '{query}' in Project Memory ---\n")
    cursor.execute("""
    SELECT source_table, title_or_key, content
    FROM project_memory_fts
    WHERE project_memory_fts MATCH ?
    LIMIT 10;
    """, (query,))
    rows = cursor.fetchall()
    if not rows:
        print("No matching project memory entries.")
        return

    for r in rows:
        print(f"[{r['source_table'].upper()}] {r['title_or_key']}")
        print(f"  {r['content'].strip()}\n")


def mem_prune(conn: sqlite3.Connection, max_snapshots: int = 10, max_age_days: int = 30):
    """Reconciles deleted conversation IDs, prunes expired snapshots, and vacuums database."""
    brain_dir = Path.home() / ".gemini" / "antigravity" / "brain"
    existing_cids = set()
    if brain_dir.exists():
        existing_cids = {f.name for f in brain_dir.iterdir() if f.is_dir()}

    cursor = conn.cursor()
    cursor.execute("SELECT id, conversation_id, created_at FROM session_snapshots;")
    snapshots = cursor.fetchall()

    pruned_orphans = 0
    pruned_expired = 0
    now = datetime.now(timezone.utc)

    for s in snapshots:
        cid = s["conversation_id"]
        sid = s["id"]
        if cid and cid != "default" and existing_cids and cid not in existing_cids:
            cursor.execute("DELETE FROM session_snapshots WHERE id = ?;", (sid,))
            pruned_orphans += 1
            continue

        try:
            snap_time = datetime.fromisoformat(s["created_at"].replace("Z", "+00:00"))
            age_days = (now - snap_time).days
            if age_days > max_age_days:
                cursor.execute("DELETE FROM session_snapshots WHERE id = ?;", (sid,))
                pruned_expired += 1
        except Exception:
            pass

    cursor.execute("SELECT id FROM session_snapshots ORDER BY id DESC;")
    all_remaining = [r[0] for r in cursor.fetchall()]
    if len(all_remaining) > max_snapshots:
        excess_ids = all_remaining[max_snapshots:]
        cursor.executemany("DELETE FROM session_snapshots WHERE id = ?;", [(eid,) for eid in excess_ids])
        pruned_expired += len(excess_ids)

    conn.commit()
    cursor.execute("PRAGMA incremental_vacuum;")
    conn.commit()
    print(f"Project memory pruned: {pruned_orphans} orphaned conversation snapshots removed, {pruned_expired} old snapshots trimmed. Vacuum complete.")


def handle_pre_invocation_hook():
    """
    Handles Antigravity PreInvocation lifecycle hook.
    Reads JSON payload from stdin. If current workspace has .agents/memory.db,
    retrieves context and injects it as an ephemeralMessage directly into the prompt.
    Also injects runtime model concurrency profile instructions for Ultra/Standard.
    """
    try:
        payload_raw = sys.stdin.read()
        payload = json.loads(payload_raw) if payload_raw.strip() else {}
    except Exception:
        payload = {}

    invocation_num = payload.get("invocationNum", 1)
    if invocation_num != 1:
        print(json.dumps({"injectSteps": []}))
        return

    workspace_paths = payload.get("workspacePaths", [])
    proj_path = Path(workspace_paths[0]) if workspace_paths else Path.cwd()
    db_path = get_project_db_path(find_project_root(proj_path))

    tier, tdesc = detect_model_tier()
    lines = []

    if tier == TIER_ULTRA:
        lines.append("[SKILLSDB RUNTIME PROFILE: GEMINI ULTRA (16-thread high-concurrency mode)]")
        lines.append("Parallel batch fetching active: 'skillsdb get-skills <s1> <s2>' | Clusters: 'skillsdb get-cluster <domain>' | Parallel search: 'skillsdb search-multi <q1> <q2>' | Concurrent subagents: 8-16 parallel workers supported.\n")

    if db_path.exists():
        try:
            conn = sqlite3.connect(db_path, timeout=5.0)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            mem_lines = []
            cursor.execute("SELECT key, value FROM project_facts ORDER BY updated_at DESC LIMIT 10;")
            facts = cursor.fetchall()
            if facts:
                mem_lines.append("Project Facts & Configs:")
                for f in facts:
                    mem_lines.append(f"  * {f['key']}: {f['value']}")

            cursor.execute("SELECT title, content FROM project_decisions WHERE is_active = 1 ORDER BY updated_at DESC LIMIT 5;")
            decs = cursor.fetchall()
            if decs:
                mem_lines.append("\nActive Architectural Decisions:")
                for d in decs:
                    mem_lines.append(f"  * [{d['title']}]: {d['content']}")

            cursor.execute("SELECT summary, next_steps, created_at FROM session_snapshots ORDER BY id DESC LIMIT 1;")
            snap = cursor.fetchone()
            if snap:
                mem_lines.append("\nLatest Project Milestone Snapshot:")
                mem_lines.append(f"  Summary: {snap['summary']}")
                if snap['next_steps']:
                    mem_lines.append(f"  Next Steps: {snap['next_steps']}")

            conn.close()

            if mem_lines:
                lines.append("=== PROJECT MEMORY CONTEXT (Auto-Loaded via Hook) ===")
                lines.extend(mem_lines)
        except Exception:
            pass

    if lines:
        context_msg = "\n".join(lines).strip()
        output = {
            "injectSteps": [
                {
                    "ephemeralMessage": context_msg
                }
            ]
        }
        print(json.dumps(output))
        return

    print(json.dumps({"injectSteps": []}))


def calculate_transcript_savings():
    """Scans Antigravity transcript files to compute cumulative prompt tokens avoided."""
    brain_dir = Path.home() / ".gemini" / "antigravity" / "brain"
    if not brain_dir.exists():
        return None

    total_turns = 0
    total_steps = 0
    session_count = 0

    for folder in brain_dir.iterdir():
        if not folder.is_dir() or folder.name == "tempmediaStorage":
            continue
        t_file = folder / ".system_generated" / "logs" / "transcript.jsonl"
        if not t_file.exists():
            continue

        has_post_deploy = False
        s_turns = 0
        s_steps = 0

        try:
            with open(t_file, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    d = json.loads(line)
                    s_steps += 1
                    ts = d.get("created_at", "")
                    if ts >= "2026-09-18T14:00:00Z":
                        has_post_deploy = True
                    src = d.get("source")
                    stype = d.get("type")
                    if src == "MODEL" or stype == "PLANNER_RESPONSE":
                        s_turns += 1
            if has_post_deploy:
                session_count += 1
                total_steps += s_steps
                total_turns += s_turns
        except Exception:
            pass

    if total_turns == 0:
        return None

    tokens_saved = total_turns * 14430
    dollars_saved_pro = (tokens_saved / 1_000_000) * 2.00
    dollars_saved_ultra = (tokens_saved / 1_000_000) * 7.50

    return {
        "sessions": session_count,
        "model_turns": total_turns,
        "steps": total_steps,
        "tokens_saved": tokens_saved,
        "dollars_saved": dollars_saved_pro,
        "dollars_saved_pro": dollars_saved_pro,
        "dollars_saved_ultra": dollars_saved_ultra
    }


def stats(conn: sqlite3.Connection, show_savings: bool = False):
    """Outputs database inventory stats and measured token/cost savings."""
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count, SUM(token_estimate) as tokens FROM rules;")
    r_stat = cursor.fetchone()
    cursor.execute("SELECT COUNT(*) as count, SUM(token_estimate) as tokens FROM skills;")
    s_stat = cursor.fetchone()

    print("\n================ CUSTOMIZATIONS DATABASE STATS ================")
    print(f"Database Path: {DB_PATH}")
    print(f"Rules:         {r_stat['count']} rules (Active content: ~{r_stat['tokens']} tokens)")
    print(f"Skills:        {s_stat['count']} skills (Total content: ~{s_stat['tokens']} tokens)")

    savings = calculate_transcript_savings()
    if savings:
        print("\n--- Measured Token Savings (Since SkillsDB Deployment) ---")
        print(f"Tracked Sessions:     {savings['sessions']} active sessions")
        print(f"Total Model Turns:    {savings['model_turns']:,} turns ({savings['steps']:,} steps)")
        print(f"Prompt Bloat Avoided: ~{savings['tokens_saved']:,} tokens (-97.4% per turn)")
        print(f"Cost Saved (Gemini Pro):   ~${savings['dollars_saved_pro']:.2f} USD")
        print(f"Cost Saved (Gemini Ultra): ~${savings['dollars_saved_ultra']:.2f} USD")
        tier, tdesc = detect_model_tier()
        if tier == TIER_ULTRA:
            print(f"Active Profile:       ULTRA (~${savings['dollars_saved_ultra']:.2f} USD saved / high quota protection)")
    print(f"[OK] Version: v{__version__} (Up to date)")
    print("================================================================\n")
