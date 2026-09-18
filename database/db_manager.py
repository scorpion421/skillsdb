#!/usr/bin/env python3
"""
Antigravity Centralized Customizations & Knowledge Database Manager.
Manages all rules, skills, and guidelines in a persistent SQLite database with FTS5 search.
Allows Antigravity agents to query rules and workflow skills on-demand without prompt bloat.
Fully generalized: automatically detects the current user's home directory and domain account.
"""

import os
import sys
import re
import json
import shutil
import sqlite3
import argparse
from datetime import datetime, timezone
from pathlib import Path

# Dynamically resolve user-relative paths
GEMINI_DIR = Path.home() / ".gemini"
DB_DIR = GEMINI_DIR / "database"
DB_PATH = DB_DIR / "customizations.db"
GLOBAL_PLUGINS_PATH = GEMINI_DIR / "config" / "plugins"
ARCHIVED_PLUGINS_PATH = GEMINI_DIR / "plugins_archive"
BUILTIN_SKILLS_PATH = GEMINI_DIR / "antigravity" / "builtin" / "skills"

# Default network share fallback for team synchronization
DEFAULT_REMOTE_SHARE = Path(r"Q:\Antigravity\SkillsDB\database\customizations.db")


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for high-concurrency and fast reads
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn


def init_db(conn: sqlite3.Connection):
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        category TEXT DEFAULT 'general',
        scope TEXT DEFAULT 'global',
        is_active INTEGER DEFAULT 1,
        summary TEXT,
        content TEXT NOT NULL,
        token_estimate INTEGER DEFAULT 0,
        updated_at TEXT
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS skills (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        plugin_name TEXT NOT NULL,
        category TEXT DEFAULT 'workflow',
        is_active INTEGER DEFAULT 1,
        description TEXT,
        content TEXT NOT NULL,
        token_estimate INTEGER DEFAULT 0,
        updated_at TEXT
    );
    """)

    cursor.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS rules_fts USING fts5(
        key,
        name,
        category,
        summary,
        content,
        content='rules',
        content_rowid='id'
    );
    """)

    cursor.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS skills_fts USING fts5(
        name,
        plugin_name,
        category,
        description,
        content,
        content='skills',
        content_rowid='id'
    );
    """)

    conn.commit()


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // 4)


def parse_skill_frontmatter(content: str):
    name = ""
    description = ""
    match = re.search(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if match:
        frontmatter = match.group(1)
        name_match = re.search(r"^name:\s*(.+)$", frontmatter, re.MULTILINE)
        if name_match:
            name = name_match.group(1).strip().strip("\"'")
        desc_match = re.search(r"^description:\s*(?:[>|-]\s*\n)?(.*?)(?=\n[a-zA-Z0-9_-]+:|$)", frontmatter, re.DOTALL | re.MULTILINE)
        if desc_match:
            desc_raw = desc_match.group(1).strip()
            description = " ".join([line.strip() for line in desc_raw.splitlines() if line.strip()])
    return name, description


def add_or_update_rule(conn: sqlite3.Connection, key: str, name: str, category: str, content: str, summary: str = None, scope: str = "global"):
    cursor = conn.cursor()
    now_iso = datetime.now(timezone.utc).isoformat()
    tokens = estimate_tokens(content)

    cursor.execute("""
    INSERT OR REPLACE INTO rules (key, name, category, scope, is_active, summary, content, token_estimate, updated_at)
    VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?)
    """, (key, name, category, scope, summary or name, content, tokens, now_iso))
    rule_id = cursor.lastrowid

    # Re-index FTS
    cursor.execute("DELETE FROM rules_fts WHERE rowid = ?;", (rule_id,))
    cursor.execute("""
    INSERT INTO rules_fts (rowid, key, name, category, summary, content)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (rule_id, key, name, category, summary or name, content))

    conn.commit()
    print(f"Rule '{key}' saved successfully (~{tokens} tokens).")


def add_or_update_skill(conn: sqlite3.Connection, name: str, description: str, content: str, plugin_name: str = "custom", category: str = "workflow"):
    cursor = conn.cursor()
    now_iso = datetime.now(timezone.utc).isoformat()
    tokens = estimate_tokens(content)

    cursor.execute("""
    INSERT OR REPLACE INTO skills (name, plugin_name, category, is_active, description, content, token_estimate, updated_at)
    VALUES (?, ?, ?, 1, ?, ?, ?, ?)
    """, (name, plugin_name, category, description, content, tokens, now_iso))
    skill_id = cursor.lastrowid

    # Re-index FTS
    cursor.execute("DELETE FROM skills_fts WHERE rowid = ?;", (skill_id,))
    cursor.execute("""
    INSERT INTO skills_fts (rowid, name, plugin_name, category, description, content)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (skill_id, name, plugin_name, category, description, content))

    conn.commit()
    print(f"Skill '{name}' saved successfully (~{tokens} tokens).")


def import_file(conn: sqlite3.Connection, file_path_str: str):
    path = Path(file_path_str)
    if not path.exists():
        print(f"Error: File not found at {path}")
        return

    content = path.read_text(encoding="utf-8", errors="replace")
    name, description = parse_skill_frontmatter(content)

    if name and description:
        add_or_update_skill(conn, name=name, description=description, content=content, plugin_name="imported", category="imported")
    else:
        key = path.stem.lower().replace(" ", "-")
        add_or_update_rule(conn, key=key, name=path.stem, category="imported", content=content, summary=f"Imported from {path.name}")


def remove_item(conn: sqlite3.Connection, item_type: str, identifier: str):
    cursor = conn.cursor()
    if item_type == "skill":
        cursor.execute("SELECT id FROM skills WHERE name = ?;", (identifier,))
        row = cursor.fetchone()
        if row:
            cursor.execute("DELETE FROM skills WHERE id = ?;", (row["id"],))
            cursor.execute("DELETE FROM skills_fts WHERE rowid = ?;", (row["id"],))
            conn.commit()
            print(f"Skill '{identifier}' removed.")
        else:
            print(f"Skill '{identifier}' not found.")
    elif item_type == "rule":
        cursor.execute("SELECT id FROM rules WHERE key = ?;", (identifier,))
        row = cursor.fetchone()
        if row:
            cursor.execute("DELETE FROM rules WHERE id = ?;", (row["id"],))
            cursor.execute("DELETE FROM rules_fts WHERE rowid = ?;", (row["id"],))
            conn.commit()
            print(f"Rule '{identifier}' removed.")
        else:
            print(f"Rule '{identifier}' not found.")


def suggest_skills(conn: sqlite3.Connection, task_description: str, limit: int = 3, as_json: bool = False):
    cursor = conn.cursor()
    # Clean query into keywords for FTS5
    words = re.findall(r"[a-zA-Z0-9_-]{3,}", task_description)
    if not words:
        if as_json:
            print("[]")
        else:
            print("No searchable keywords identified.")
        return

    fts_query = " OR ".join(words[:12])

    cursor.execute("""
    SELECT s.name, s.plugin_name, s.category, s.description, s.token_estimate, rank
    FROM skills_fts f
    JOIN skills s ON f.rowid = s.id
    WHERE skills_fts MATCH ?
    ORDER BY rank
    LIMIT ?;
    """, (fts_query, limit))
    matches = cursor.fetchall()

    if as_json:
        result = [dict(m) for m in matches]
        print(json.dumps(result, indent=2))
        return

    print(f"\n--- Recommended Skills for: '{task_description}' ---\n")
    if not matches:
        print("No specific workflow skills matched this task.")
        return

    for idx, m in enumerate(matches, 1):
        desc = (m["description"][:110] + "...") if m["description"] and len(m["description"]) > 110 else m["description"]
        print(f"{idx}. [{m['plugin_name']}] {m['name']} (~{m['token_estimate']} tokens)")
        print(f"   Desc: {desc}")
        print(f"   Command to view: python ~/.gemini/database/db_manager.py get-skill {m['name']}\n")


def sync_database(conn: sqlite3.Connection, direction: str, remote_path_str: str = None):
    remote_path = Path(remote_path_str) if remote_path_str else DEFAULT_REMOTE_SHARE

    if direction == "push":
        # Create remote parent dir if needed
        remote_path.parent.mkdir(parents=True, exist_ok=True)
        # Check if remote exists, make backup first
        if remote_path.exists():
            bak_path = remote_path.with_suffix(f".bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            shutil.copy2(remote_path, bak_path)
            print(f"Created remote backup at: {bak_path}")

        # Checkpoint local WAL before copying
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        shutil.copy2(DB_PATH, remote_path)
        print(f"Local database successfully pushed to: {remote_path}")

    elif direction == "pull":
        if not remote_path.exists():
            print(f"Error: Remote database not found at: {remote_path}")
            return

        # Backup local before pulling
        if DB_PATH.exists():
            bak_path = DB_PATH.with_suffix(f".bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            shutil.copy2(DB_PATH, bak_path)
            print(f"Created local backup at: {bak_path}")

        conn.close()
        shutil.copy2(remote_path, DB_PATH)
        print(f"Remote database pulled successfully from: {remote_path}")


def import_from_plugins(conn: sqlite3.Connection):
    init_db(conn)
    cursor = conn.cursor()

    now_iso = datetime.now(timezone.utc).isoformat()

    cursor.execute("DELETE FROM rules_fts;")
    cursor.execute("DELETE FROM skills_fts;")
    cursor.execute("DELETE FROM rules;")
    cursor.execute("DELETE FROM skills;")

    rules_count = 0
    skills_count = 0

    rule_configs = [
        {
            "key": "communication-style",
            "name": "Communication Style (German Du-Form)",
            "category": "communication",
            "path": GLOBAL_PLUGINS_PATH / "communication-style" / "rules" / "AGENTS.md",
            "summary": "Always use informal 'Du' in German. Never use formal 'Sie'."
        },
        {
            "key": "local-admin",
            "name": "Local Admin Elevation (DPAPI)",
            "category": "security",
            "path": GLOBAL_PLUGINS_PATH / "local-admin" / "rules" / "AGENTS.md",
            "summary": "Use encrypted DPAPI credentials for the user's .adm account (<DOMAIN>\\<USERNAME>.adm) via Invoke-Command without UAC."
        },
        {
            "key": "scripting-rules",
            "name": "Global Scripting Standards",
            "category": "coding-standards",
            "path": GLOBAL_PLUGINS_PATH / "scripting-rules" / "rules" / "AGENTS.md",
            "summary": "English only, no emojis, no em/en-dashes, no fluff, proper error handling, strictly no VBScript."
        },
        {
            "key": "token-efficiency",
            "name": "Token Efficiency & Context Hygiene",
            "category": "performance",
            "path": None,
            "content": """# Token Efficiency and Context Hygiene Standards

To maximize performance, reduce latency, and prevent context rot, the agent must strictly enforce the following token conservation standards across all operations:

## 1. Command Output Hygiene
Terminal and CLI outputs consume significant tokens and persist across the entire conversation history.
- Git Operations:
  - Always use `git status --short` (or `-s`) instead of verbose `git status`.
  - Always limit log queries, e.g., `git log -n 5 --oneline` instead of unbounded `git log`.
  - Use `git diff --stat` first to assess scope before viewing full diffs.
- PowerShell & Terminal Queries:
  - Always bound collection outputs: pipe to `Select-Object -First <N>` or use targeted `-Filter` / `-Property` parameters.
  - Suppress verbose build, package restore, or installation noise with `--quiet`, `--silent`, or redirection when appropriate.
  - Avoid dumping binary files, massive log dumps, or full directory trees to stdout.

## 2. Targeted File Inspection (No Full-File Dumps)
- Slice Reading: Never read entire large files (>100 lines) with `view_file` when only inspecting or editing a specific component.
- Pinpoint with Grep First: Use `grep_search` to locate exact symbol or function line numbers.
- Inspect Slices: Call `view_file` using explicit `StartLine` and `EndLine` ranges (e.g. 30-50 lines surrounding the target).
- Chunk Replacement: Always modify code using surgical chunk replacements via `replace_file_content` instead of rewriting entire files.

## 3. Context Isolation via Subagents
- When an operation requires high-iteration discovery, deep codebase exploration (inspecting dozens of candidate files), or large log analysis, delegate the task to a lightweight subagent (`invoke_subagent`).
- The subagent absorbs the context bloat within its isolated session and returns only the concise distilled result to the primary conversation.

## 4. Concise Output Generation
- Output tokens are significantly more computationally expensive and slower to generate than input tokens.
- Keep prose answers direct, factual, and actionable.
- Eliminate conversational preamble, polite filler phrases, and restating what the user just said.
- Provide targeted code diffs and clickable file links (`file:///...`) rather than reprinting complete files.
""",
            "summary": "Mandatory practices to minimize token burn: command output limiting, line-sliced file reads, subagent isolation, and concise outputs."
        },
        {
            "key": "project-memory",
            "name": "Project Memory & Continuity Standards",
            "category": "workflow",
            "path": None,
            "content": """# Project Memory and Continuity Standards

In persistent project workspaces, the agent maintains an embedded SQLite knowledge base in `.agents/memory.db` to preserve architectural decisions, key facts, and milestone snapshots across sessions.

## 1. When to Engage Project Memory
- **Engage Memory (Non-Trivial Tasks)**:
  - Multi-step tasks, architectural refactoring, system setup, or extended interactive conversations.
  - Multi-turn debugging or cross-file feature implementations.
  - At the start of such tasks: run `skillsdb mem-get-context` to retrieve project facts and the latest milestone (auto-initializes if missing).
  - Upon completing significant work or ending a session: run `skillsdb mem-save-snapshot "<summary>"`.
- **Skip Memory (Zero Overhead for Trivial Queries)**:
  - Single-turn, trivial questions (e.g., "What does this command do?", "Explain this regex", "Format this table").
  - General conceptual explanations without changes to project code or configuration.
  - Do not create `.agents/` or execute memory queries for ad-hoc, ephemeral queries.

## 2. Memory Commands
- `skillsdb mem-get-context` : Retrieve recent milestone snapshot, active architectural decisions, and key project facts.
- `skillsdb mem-save-snapshot "<summary>"` : Persist completed milestones and next steps.
- `skillsdb mem-save-decision "<title>" "<content>" [category]` : Persist a lasting architectural decision.
- `skillsdb mem-save-fact "<key>" "<value>"` : Persist a key configuration or environment fact.
- `skillsdb mem-search "<query>"` : Search project memory via FTS5 full-text index.
""",
            "summary": "Maintain .agents/memory.db for multi-step tasks and architectural milestones; omit for trivial one-off queries."
        }
    ]

    for rc in rule_configs:
        content = rc.get("content")
        if not content and rc.get("path"):
            candidate = rc["path"]
            if not candidate.exists() and ARCHIVED_PLUGINS_PATH.exists():
                try:
                    alt = ARCHIVED_PLUGINS_PATH / candidate.relative_to(GLOBAL_PLUGINS_PATH)
                    if alt.exists():
                        candidate = alt
                except ValueError:
                    pass
            if candidate.exists():
                content = candidate.read_text(encoding="utf-8", errors="replace")
        if content:
            tokens = estimate_tokens(content)
            cursor.execute("""
            INSERT INTO rules (key, name, category, scope, is_active, summary, content, token_estimate, updated_at)
            VALUES (?, ?, ?, 'global', 1, ?, ?, ?, ?)
            """, (rc["key"], rc["name"], rc["category"], rc["summary"], content, tokens, now_iso))
            rule_id = cursor.lastrowid
            cursor.execute("""
            INSERT INTO rules_fts (rowid, key, name, category, summary, content)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (rule_id, rc["key"], rc["name"], rc["category"], rc["summary"], content))
            rules_count += 1

    plugin_sources = [p for p in [GLOBAL_PLUGINS_PATH, ARCHIVED_PLUGINS_PATH] if p.exists()]
    for base_dir in plugin_sources:
        for plugin_dir in base_dir.iterdir():
            if not plugin_dir.is_dir() or plugin_dir.name in ["communication-style", "local-admin", "scripting-rules", "customizations-db"]:
                continue
            rules_dir = plugin_dir / "rules"
            if rules_dir.exists():
                for rf in rules_dir.glob("*.md"):
                    key = f"{plugin_dir.name}-{rf.stem}"
                    content = rf.read_text(encoding="utf-8", errors="replace")
                    tokens = estimate_tokens(content)
                    cursor.execute("""
                    INSERT OR REPLACE INTO rules (key, name, category, scope, is_active, summary, content, token_estimate, updated_at)
                    VALUES (?, ?, ?, 'plugin', 1, ?, ?, ?, ?)
                    """, (key, f"{plugin_dir.name}: {rf.name}", plugin_dir.name, f"Rule from {plugin_dir.name}", content, tokens, now_iso))
                    rule_id = cursor.lastrowid
                    cursor.execute("""
                    INSERT INTO rules_fts (rowid, key, name, category, summary, content)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """, (rule_id, key, f"{plugin_dir.name}: {rf.name}", plugin_dir.name, f"Rule from {plugin_dir.name}", content))
                    rules_count += 1

    for base_dir in plugin_sources:
        for plugin_dir in base_dir.iterdir():
            if not plugin_dir.is_dir():
                continue
            skills_dir = plugin_dir / "skills"
            if skills_dir.exists():
                for sf in skills_dir.rglob("SKILL.md"):
                    content = sf.read_text(encoding="utf-8", errors="replace")
                    name, desc = parse_skill_frontmatter(content)
                    if not name:
                        name = sf.parent.name if sf.parent.name != "skills" else plugin_dir.name
                    tokens = estimate_tokens(content)
                    try:
                        cursor.execute("""
                        INSERT OR REPLACE INTO skills (name, plugin_name, category, is_active, description, content, token_estimate, updated_at)
                        VALUES (?, ?, ?, 1, ?, ?, ?, ?)
                        """, (name, plugin_dir.name, plugin_dir.name, desc, content, tokens, now_iso))
                        skill_id = cursor.lastrowid
                        cursor.execute("""
                        INSERT INTO skills_fts (rowid, name, plugin_name, category, description, content)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """, (skill_id, name, plugin_dir.name, plugin_dir.name, desc, content))
                        skills_count += 1
                    except Exception as err:
                        print(f"Error inserting skill {name}: {err}")

    if BUILTIN_SKILLS_PATH.exists():
        for sf in BUILTIN_SKILLS_PATH.rglob("SKILL.md"):
            content = sf.read_text(encoding="utf-8", errors="replace")
            name, desc = parse_skill_frontmatter(content)
            if not name:
                name = sf.parent.name
            tokens = estimate_tokens(content)
            try:
                cursor.execute("""
                INSERT OR IGNORE INTO skills (name, plugin_name, category, is_active, description, content, token_estimate, updated_at)
                VALUES (?, 'builtin', 'builtin', 1, ?, ?, ?, ?)
                """, (name, desc, content, tokens, now_iso))
                skill_id = cursor.lastrowid
                if skill_id:
                    cursor.execute("""
                    INSERT INTO skills_fts (rowid, name, plugin_name, category, description, content)
                    VALUES (?, ?, 'builtin', 'builtin', ?, ?)
                    """, (skill_id, name, desc, content))
                    skills_count += 1
            except Exception as err:
                print(f"Error inserting builtin skill {name}: {err}")

    conn.commit()
    print(f"Successfully populated database with {rules_count} rules and {skills_count} skills at {DB_PATH}")


def get_active_rules(conn: sqlite3.Connection):
    cursor = conn.cursor()
    cursor.execute("""
    SELECT key, name, category, summary, content
    FROM rules
    WHERE is_active = 1
    ORDER BY id ASC;
    """)
    rows = cursor.fetchall()
    if not rows:
        print("No active rules found.")
        return

    print("========================= ACTIVE GLOBAL RULES =========================")
    for r in rows:
        print(f"\n--- [{r['category'].upper()}] {r['name']} (Key: {r['key']}) ---")
        print(r['content'].strip())
    print("\n=======================================================================")


def get_rule(conn: sqlite3.Connection, key: str):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM rules WHERE key = ? OR name LIKE ? LIMIT 1;", (key, f"%{key}%"))
    rule = cursor.fetchone()
    if not rule:
        print(f"Rule '{key}' not found in database.")
        return
    print(f"=== Rule: {rule['name']} ({rule['key']}) ===")
    print(f"Category: {rule['category']} | Scope: {rule['scope']} | Active: {bool(rule['is_active'])}")
    print(f"Token estimate: ~{rule['token_estimate']} tokens\n")
    print(rule['content'])


def get_skill(conn: sqlite3.Connection, name: str):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM skills WHERE name = ? OR name LIKE ? LIMIT 1;", (name, f"%{name}%"))
    skill = cursor.fetchone()
    if not skill:
        print(f"Skill '{name}' not found in database.")
        return
    print(f"=== Skill: {skill['name']} (Plugin: {skill['plugin_name']}) ===")
    print(f"Category: {skill['category']} | Active: {bool(skill['is_active'])}")
    print(f"Token estimate: ~{skill['token_estimate']} tokens\n")
    print(skill['content'])


def search(conn: sqlite3.Connection, query: str):
    cursor = conn.cursor()
    print(f"\n--- Search results for '{query}' in Customizations Database ---\n")

    cursor.execute("""
    SELECT r.key, r.name, r.category, r.summary, r.token_estimate
    FROM rules_fts f
    JOIN rules r ON f.rowid = r.id
    WHERE rules_fts MATCH ?
    ORDER BY rank
    LIMIT 10;
    """, (query,))
    rules = cursor.fetchall()
    if rules:
        print(f"Matching Rules ({len(rules)}):")
        for r in rules:
            print(f"  * [{r['category']}] {r['name']} (Key: {r['key']}, ~{r['token_estimate']} tokens)")
            if r['summary']:
                print(f"    Summary: {r['summary']}")
    else:
        print("No matching rules.")

    cursor.execute("""
    SELECT s.name, s.plugin_name, s.description, s.token_estimate
    FROM skills_fts f
    JOIN skills s ON f.rowid = s.id
    WHERE skills_fts MATCH ?
    ORDER BY rank
    LIMIT 10;
    """, (query,))
    skills = cursor.fetchall()
    if skills:
        print(f"\nMatching Skills ({len(skills)}):")
        for s in skills:
            desc = (s['description'][:110] + "...") if s['description'] and len(s['description']) > 110 else s['description']
            print(f"  * [{s['plugin_name']}] {s['name']} (~{s['token_estimate']} tokens)")
            print(f"    Desc: {desc}")
    else:
        print("\nNo matching skills.")


def list_all(conn: sqlite3.Connection):
    cursor = conn.cursor()
    print("\n--- ALL RULES IN DATABASE ---")
    cursor.execute("SELECT key, name, category, is_active, token_estimate FROM rules ORDER BY category, key;")
    for r in cursor.fetchall():
        status = "ACTIVE" if r["is_active"] else "INACTIVE"
        print(f"  [{status}] {r['category']:<15} {r['key']:<25} ({r['name']})")

    print("\n--- ALL SKILLS IN DATABASE (GROUPED BY PLUGIN) ---")
    cursor.execute("SELECT plugin_name, COUNT(*) as cnt, SUM(token_estimate) as tokens FROM skills GROUP BY plugin_name ORDER BY plugin_name;")
    for p in cursor.fetchall():
        print(f"  Plugin: {p['plugin_name']:<28} {p['cnt']:>3} skills (~{p['tokens']:>6} tokens)")


def export_skill(conn: sqlite3.Connection, skill_name: str, target_dir_str: str):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM skills WHERE name = ? LIMIT 1;", (skill_name,))
    skill = cursor.fetchone()
    if not skill:
        print(f"Error: Skill '{skill_name}' not found.")
        return

    target_dir = Path(target_dir_str) / ".agents" / "skills" / skill["name"]
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / "SKILL.md"
    target_file.write_text(skill["content"], encoding="utf-8")
    print(f"Skill '{skill['name']}' exported successfully to:\n{target_file}")


def stats(conn: sqlite3.Connection):
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count, SUM(token_estimate) as tokens FROM rules;")
    r_stat = cursor.fetchone()
    cursor.execute("SELECT COUNT(*) as count, SUM(token_estimate) as tokens FROM skills;")
    s_stat = cursor.fetchone()

    print("\n================ CUSTOMIZATIONS DATABASE STATS ================")
    print(f"Database Path: {DB_PATH}")
    print(f"Rules:         {r_stat['count']} rules (Active content: ~{r_stat['tokens']} tokens)")
    print(f"Skills:        {s_stat['count']} skills (Total content: ~{s_stat['tokens']} tokens)")
    print("================================================================\n")


def sync_database(conn: sqlite3.Connection, direction: str, remote_path_str: str = None):
    remote_path = Path(remote_path_str) if remote_path_str else DEFAULT_REMOTE_SHARE

    if direction == "push":
        if not DB_PATH.exists():
            print(f"Error: Local database {DB_PATH} does not exist.")
            return
        remote_path.parent.mkdir(parents=True, exist_ok=True)
        # Flush WAL before copying to ensure binary file is clean
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        shutil.copy2(DB_PATH, remote_path)
        print(f"Successfully pushed local database to network share:\n{remote_path}")
    elif direction == "pull":
        if not remote_path.exists():
            print(f"Error: Remote database {remote_path} does not exist.")
            return
        conn.close()
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(remote_path, DB_PATH)
        print(f"Successfully pulled database from network share:\n{remote_path} -> {DB_PATH}")


# ==============================================================================
# PROJECT-LEVEL EPISODIC MEMORY IMPLEMENTATION
# ==============================================================================

def find_project_root(start_path: Path = None) -> Path:
    current = (start_path or Path.cwd()).resolve()
    project_markers = [
        ".agents", ".git", ".antigravity",
        "package.json", "pyproject.toml", "requirements.txt",
        "pubspec.yaml", "go.mod", "pom.xml", "build.gradle"
    ]
    home_dir = Path.home().resolve()
    for parent in [current] + list(current.parents):
        # Stop traversing at user home directory so home is never treated as a project root
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


def mem_save_decision(conn: sqlite3.Connection, title: str, content: str, category: str = "architecture"):
    cursor = conn.cursor()
    now_iso = datetime.now(timezone.utc).isoformat()
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


def mem_save_snapshot(conn: sqlite3.Connection, summary: str, conversation_id: str = None, next_steps: str = None, files_touched: str = None):
    cursor = conn.cursor()
    now_iso = datetime.now(timezone.utc).isoformat()
    cid = conversation_id or os.environ.get("ANTIGRAVITY_CONVERSATION_ID") or "default"
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


def mem_save_fact(conn: sqlite3.Connection, key: str, value: str):
    cursor = conn.cursor()
    now_iso = datetime.now(timezone.utc).isoformat()
    cursor.execute("""
    INSERT INTO project_facts (key, value, updated_at)
    VALUES (?, ?, ?)
    ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at;
    """, (key, value, now_iso))
    cursor.execute("""
    INSERT INTO project_memory_fts (source_table, title_or_key, content)
    VALUES ('fact', ?, ?);
    """, (key, value))
    conn.commit()
    print(f"Project fact saved: '{key}' = '{value}'")


def mem_get_context(conn: sqlite3.Connection, max_decisions: int = 5):
    cursor = conn.cursor()
    print("=== PROJECT MEMORY CONTEXT ===")
    cursor.execute("""
    SELECT title, content, category FROM project_decisions
    WHERE is_active = 1
    ORDER BY id DESC LIMIT ?;
    """, (max_decisions,))
    decisions = cursor.fetchall()
    if decisions:
        print("\nActive Architectural Decisions:")
        for d in decisions:
            print(f"  * [{d['category'].upper()}] {d['title']}: {d['content']}")

    cursor.execute("""
    SELECT key, value FROM project_facts ORDER BY updated_at DESC LIMIT 10;
    """)
    facts = cursor.fetchall()
    if facts:
        print("\nProject Facts & Configs:")
        for f in facts:
            print(f"  * {f['key']}: {f['value']}")

    cursor.execute("""
    SELECT conversation_id, summary, next_steps, created_at
    FROM session_snapshots
    ORDER BY id DESC LIMIT 1;
    """)
    last_snap = cursor.fetchone()
    if last_snap:
        print(f"\nLatest Session Milestone ({last_snap['created_at'][:10]}):")
        print(f"  Summary:    {last_snap['summary']}")
        if last_snap['next_steps']:
            print(f"  Next Steps: {last_snap['next_steps']}")
    print("==============================\n")


def mem_search(conn: sqlite3.Connection, query: str):
    cursor = conn.cursor()
    cursor.execute("""
    SELECT source_table, title_or_key, content
    FROM project_memory_fts
    WHERE project_memory_fts MATCH ?
    ORDER BY rank
    LIMIT 10;
    """, (query,))
    rows = cursor.fetchall()
    print(f"=== Project Memory Search for: '{query}' ({len(rows)} matches) ===")
    for r in rows:
        print(f"  [{r['source_table'].upper()}] {r['title_or_key']}: {r['content']}")
    print("=================================================================\n")


def mem_prune(conn: sqlite3.Connection, max_snapshots: int = 10, max_age_days: int = 30):
    cursor = conn.cursor()
    brain_dir = Path.home() / ".gemini" / "antigravity" / "brain"
    pruned_orphans = 0
    pruned_expired = 0

    # 1. Orphan pruning: Check if conversation directory still exists
    if brain_dir.exists():
        cursor.execute("SELECT DISTINCT conversation_id FROM session_snapshots WHERE conversation_id != 'default';")
        cids = [r["conversation_id"] for r in cursor.fetchall()]
        for cid in cids:
            conv_path = brain_dir / cid
            if not conv_path.exists():
                cursor.execute("DELETE FROM session_snapshots WHERE conversation_id = ?;", (cid,))
                pruned_orphans += cursor.rowcount

    # 2. Rolling window pruning: Keep only last max_snapshots
    cursor.execute("SELECT id, created_at FROM session_snapshots ORDER BY id DESC;")
    snapshots = cursor.fetchall()
    if len(snapshots) > max_snapshots:
        excess_ids = [s["id"] for s in snapshots[max_snapshots:]]
        cursor.executemany("DELETE FROM session_snapshots WHERE id = ?;", [(eid,) for eid in excess_ids])
        pruned_expired += len(excess_ids)

    conn.commit()

    # 3. Incremental vacuum to reclaim storage space immediately
    cursor.execute("PRAGMA incremental_vacuum;")
    conn.commit()

    print(f"Project memory pruned: {pruned_orphans} orphaned conversation snapshots removed, {pruned_expired} old snapshots trimmed. Vacuum complete.")


def main():
    parser = argparse.ArgumentParser(description="Antigravity Central Customizations & Project Memory Manager")
    subparsers = parser.add_subparsers(dest="command")

    # Central DB Commands
    subparsers.add_parser("import-all", help="Import/re-import all rules and skills into SQLite")
    subparsers.add_parser("get-active-rules", help="Output all active global rules")
    
    get_rule_parser = subparsers.add_parser("get-rule", help="Output a specific rule")
    get_rule_parser.add_argument("key", help="Rule key")

    get_skill_parser = subparsers.add_parser("get-skill", help="Output a specific skill")
    get_skill_parser.add_argument("name", help="Skill name")

    search_parser = subparsers.add_parser("search", help="Full-text search in rules and skills")
    search_parser.add_argument("query", help="Search query")

    suggest_parser = subparsers.add_parser("suggest", help="Auto-recommend relevant skills for a user task")
    suggest_parser.add_argument("task", help="Description of the task")
    suggest_parser.add_argument("--json", action="store_true", help="Output as JSON")

    import_file_parser = subparsers.add_parser("import-file", help="Import any markdown skill or rule file")
    import_file_parser.add_argument("file_path", help="Path to markdown file")

    remove_parser = subparsers.add_parser("remove", help="Remove an item from the database")
    remove_parser.add_argument("type", choices=["skill", "rule"], help="Item type")
    remove_parser.add_argument("name", help="Item name or key")

    sync_parser = subparsers.add_parser("sync", help="Synchronize database with network team share")
    sync_parser.add_argument("direction", choices=["push", "pull"], help="Sync direction")
    sync_parser.add_argument("--remote", default=None, help="Remote database path (optional)")

    subparsers.add_parser("list", help="List all rules and plugins/skills summary")
    subparsers.add_parser("stats", help="Show database statistics")

    export_parser = subparsers.add_parser("export-skill", help="Export a skill into a project workspace")
    export_parser.add_argument("name", help="Skill name")
    export_parser.add_argument("target", help="Target project root directory")

    # Project Memory Commands
    mem_init_parser = subparsers.add_parser("mem-init", help="Initialize project memory database (.agents/memory.db)")
    mem_init_parser.add_argument("--project", default=None, help="Project root directory (optional)")

    mem_dec_parser = subparsers.add_parser("mem-save-decision", help="Save an architectural or setup decision")
    mem_dec_parser.add_argument("title", help="Decision title")
    mem_dec_parser.add_argument("content", help="Decision content/rationale")
    mem_dec_parser.add_argument("--category", default="architecture", help="Category (default: architecture)")
    mem_dec_parser.add_argument("--project", default=None, help="Project root directory (optional)")

    mem_snap_parser = subparsers.add_parser("mem-save-snapshot", help="Save a session milestone snapshot")
    mem_snap_parser.add_argument("summary", help="Summary of work completed")
    mem_snap_parser.add_argument("--cid", default=None, help="Antigravity conversation ID")
    mem_snap_parser.add_argument("--next-steps", default=None, help="Next steps or open items")
    mem_snap_parser.add_argument("--files", default=None, help="Key files touched")
    mem_snap_parser.add_argument("--project", default=None, help="Project root directory (optional)")

    mem_fact_parser = subparsers.add_parser("mem-save-fact", help="Save a key-value fact or configuration")
    mem_fact_parser.add_argument("key", help="Fact key")
    mem_fact_parser.add_argument("value", help="Fact value")
    mem_fact_parser.add_argument("--project", default=None, help="Project root directory (optional)")

    mem_ctx_parser = subparsers.add_parser("mem-get-context", help="Retrieve compact project context")
    mem_ctx_parser.add_argument("--project", default=None, help="Project root directory (optional)")

    mem_srch_parser = subparsers.add_parser("mem-search", help="Search project memory")
    mem_srch_parser.add_argument("query", help="Search query")
    mem_srch_parser.add_argument("--project", default=None, help="Project root directory (optional)")

    mem_prune_parser = subparsers.add_parser("mem-prune", help="Prune deleted conversation snapshots and vacuum DB")
    mem_prune_parser.add_argument("--max-snapshots", type=int, default=10, help="Maximum snapshots to keep")
    mem_prune_parser.add_argument("--max-age", type=int, default=30, help="Max age in days")
    mem_prune_parser.add_argument("--project", default=None, help="Project root directory (optional)")

    args = parser.parse_args()

    # Route project memory commands directly to project database
    if args.command and args.command.startswith("mem-"):
        proj_root = Path(args.project) if getattr(args, "project", None) else find_project_root()
        if args.command == "mem-init":
            mem_init(proj_root)
            return

        pconn = get_project_connection(proj_root)
        init_project_db(pconn)

        if args.command == "mem-save-decision":
            mem_save_decision(pconn, args.title, args.content, args.category)
        elif args.command == "mem-save-snapshot":
            mem_save_snapshot(pconn, args.summary, conversation_id=args.cid, next_steps=args.next_steps, files_touched=args.files)
        elif args.command == "mem-save-fact":
            mem_save_fact(pconn, args.key, args.value)
        elif args.command == "mem-get-context":
            mem_get_context(pconn)
        elif args.command == "mem-search":
            mem_search(pconn, args.query)
        elif args.command == "mem-prune":
            mem_prune(pconn, max_snapshots=args.max_snapshots, max_age_days=args.max_age)

        pconn.close()
        return

    # Route central DB commands
    conn = get_connection()
    init_db(conn)

    if args.command == "import-all" or not args.command:
        import_from_plugins(conn)
    elif args.command == "get-active-rules":
        get_active_rules(conn)
    elif args.command == "get-rule":
        get_rule(conn, args.key)
    elif args.command == "get-skill":
        get_skill(conn, args.name)
    elif args.command == "search":
        search(conn, args.query)
    elif args.command == "suggest":
        suggest_skills(conn, args.task, as_json=args.json)
    elif args.command == "import-file":
        import_file(conn, args.file_path)
    elif args.command == "remove":
        remove_item(conn, args.type, args.name)
    elif args.command == "sync":
        sync_database(conn, args.direction, args.remote)
    elif args.command == "list":
        list_all(conn)
    elif args.command == "stats":
        stats(conn)
    elif args.command == "export-skill":
        export_skill(conn, args.name, args.target)

    conn.close()


if __name__ == "__main__":
    main()
