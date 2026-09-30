"""
SkillsDB command-line interface argument parsing and dispatching.
"""

import sys
import argparse
from pathlib import Path

from .config import SKILL_CLUSTERS, DB_PATH
from .core.db import get_connection, init_db
from .core.detector import get_profile, set_profile
from .core.concurrency import (
    get_skills_parallel,
    search_multi_parallel,
    get_cluster,
    benchmark_concurrency,
)
from .search.synonyms import init_synonyms
from .search.fts import (
    suggest_skills,
    search,
    get_skill,
    get_active_rules,
    get_rule,
    list_all,
    export_skill,
)
from .memory.project_memory import (
    find_project_root,
    get_project_connection,
    init_project_db,
    mem_init,
    mem_save_decision,
    mem_save_snapshot,
    mem_save_fact,
    mem_get_context,
    mem_search,
    mem_prune,
    handle_pre_invocation_hook,
    stats,
)
from .updater.merger import (
    doctor,
    check_update,
    update_plugin,
    import_from_plugins,
    learn_rule,
    import_file,
    remove_item,
    sync_database,
)
from .platform.windows_utf8 import fix_utf8


def build_parser() -> argparse.ArgumentParser:
    """Builds and returns the argparse ArgumentParser for SkillsDB."""
    parser = argparse.ArgumentParser(
        prog="skillsdb",
        description="SkillsDB: Central Customizations, Autonomous Project Memory & High-Concurrency Knowledge Engine for Google Antigravity",
    )
    subparsers = parser.add_subparsers(dest="command")

    # Central Database Commands
    subparsers.add_parser("import-all", help="Import/re-import all rules and skills into SQLite")
    subparsers.add_parser("get-active-rules", help="Output all active global rules")

    get_rule_parser = subparsers.add_parser("get-rule", help="Output a specific rule")
    get_rule_parser.add_argument("key", help="Rule key")

    get_skill_parser = subparsers.add_parser("get-skill", help="Output a specific skill or micro-skill section")
    get_skill_parser.add_argument("name", help="Skill name")
    get_skill_parser.add_argument("--summary", action="store_true", help="Output only skill outline and section list (~80 tokens)")
    get_skill_parser.add_argument("--section", default=None, help="Output only a specific section/micro-skill (~150-300 tokens)")

    learn_rule_parser = subparsers.add_parser("learn-rule", help="Persist a new learned rule into central database")
    learn_rule_parser.add_argument("key", help="Unique rule key")
    learn_rule_parser.add_argument("name", help="Rule name")
    learn_rule_parser.add_argument("content", help="Rule markdown content")
    learn_rule_parser.add_argument("--category", default="learned", help="Rule category")
    learn_rule_parser.add_argument("--scope", default="global", help="Rule scope")

    subparsers.add_parser("doctor", help="Run system diagnostics and verify installation health")

    fix_utf8_parser = subparsers.add_parser("fix-utf8", help="Configure Antigravity to run natively with UTF-8 code page on Windows")
    fix_utf8_parser.add_argument("--check", action="store_true", help="Only check UTF-8 status without modifying files")

    subparsers.add_parser("check-update", help="Check for available SkillsDB updates on GitHub")

    update_parser = subparsers.add_parser("update", help="Safely update SkillsDB to the latest version without data loss")
    update_parser.add_argument("--force", action="store_true", help="Force update even if on latest version")
    update_parser.add_argument("--check", action="store_true", help="Only check for updates (alias for check-update)")

    subparsers.add_parser("mem-pre-invocation-hook", help="Internal Antigravity lifecycle hook handler")

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

    stats_parser = subparsers.add_parser("stats", help="Show database statistics and token savings")
    stats_parser.add_argument("--savings", action="store_true", help="Display measured token and cost savings")

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

    # Model Profile Commands
    profile_parser = subparsers.add_parser("profile", help="View or configure model tier concurrency profile (ultra, standard, lean, auto)")
    profile_parser.add_argument("action", nargs="?", default="get", choices=["get", "set", "auto"], help="Profile action (default: get)")
    profile_parser.add_argument("tier", nargs="?", default=None, help="Model tier when action is 'set' (ultra, standard, lean)")

    # Parallel Concurrency Commands
    get_skills_parser = subparsers.add_parser("get-skills", help="Retrieve multiple skills concurrently in a single batch call")
    get_skills_parser.add_argument("names", nargs="+", help="Skill names to retrieve concurrently")
    get_skills_parser.add_argument("--summary", action="store_true", help="Output only outlines and section lists")
    get_skills_parser.add_argument("--workers", type=int, default=16, help="Max worker threads (default: 16)")
    get_skills_parser.add_argument("--json", action="store_true", help="Output results as JSON")

    search_multi_parser = subparsers.add_parser("search-multi", help="Execute multiple search queries concurrently")
    search_multi_parser.add_argument("queries", nargs="+", help="Search queries")
    search_multi_parser.add_argument("--workers", type=int, default=16, help="Max worker threads (default: 16)")
    search_multi_parser.add_argument("--limit", type=int, default=4, help="Limit per query (default: 4)")
    search_multi_parser.add_argument("--json", action="store_true", help="Output results as JSON")

    cluster_parser = subparsers.add_parser("get-cluster", help="Prefetch all skills belonging to a domain cluster concurrently")
    cluster_parser.add_argument("domain", help=f"Domain cluster ({', '.join(SKILL_CLUSTERS.keys())})")
    cluster_parser.add_argument("--summary", action="store_true", help="Output only outlines and section lists")
    cluster_parser.add_argument("--workers", type=int, default=16, help="Max worker threads (default: 16)")
    cluster_parser.add_argument("--json", action="store_true", help="Output results as JSON")

    bench_parser = subparsers.add_parser("benchmark-concurrency", help="Benchmark sequential vs. parallel multi-threaded retrieval")
    bench_parser.add_argument("--queries", type=int, default=20, help="Number of queries/skills to test (default: 20)")
    bench_parser.add_argument("--workers", type=int, default=16, help="Max worker threads (default: 16)")

    return parser


def main(argv: list[str] = None):
    """Main CLI entrypoint for SkillsDB."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "mem-pre-invocation-hook":
        handle_pre_invocation_hook()
        return

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
            mem_get_context(pconn, project_root=proj_root)
        elif args.command == "mem-search":
            mem_search(pconn, args.query)
        elif args.command == "mem-prune":
            mem_prune(pconn, max_snapshots=args.max_snapshots, max_age_days=args.max_age)

        pconn.close()
        return

    # Route central DB commands
    conn = get_connection(DB_PATH)
    init_db(conn)
    init_synonyms(conn)

    if args.command == "import-all" or not args.command:
        import_from_plugins(conn)
    elif args.command == "get-active-rules":
        get_active_rules(conn)
    elif args.command == "get-rule":
        get_rule(conn, args.key)
    elif args.command == "get-skill":
        get_skill(conn, args.name, summary=getattr(args, "summary", False), section=getattr(args, "section", None))
    elif args.command == "learn-rule":
        learn_rule(conn, args.key, args.name, args.content, category=args.category, scope=args.scope)
    elif args.command == "doctor":
        doctor(conn)
    elif args.command == "fix-utf8":
        fix_utf8(check_only=getattr(args, "check", False))
    elif args.command == "check-update":
        check_update()
    elif args.command == "update":
        if getattr(args, "check", False):
            check_update()
        else:
            update_plugin(force=getattr(args, "force", False))
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
        stats(conn, show_savings=getattr(args, "savings", False))
    elif args.command == "export-skill":
        export_skill(conn, args.name, args.target)
    elif args.command == "profile":
        if args.action == "set":
            if not args.tier:
                print("Error: Specify tier to set (ultra, standard, lean). Example: skillsdb profile set ultra")
            else:
                set_profile(args.tier, db_path=DB_PATH)
        elif args.action == "auto":
            set_profile("auto", db_path=DB_PATH)
        else:
            get_profile()
    elif args.command == "get-skills":
        get_skills_parallel(args.names, max_workers=args.workers, as_json=args.json, summary=args.summary, db_path=DB_PATH)
    elif args.command == "search-multi":
        search_multi_parallel(args.queries, max_workers=args.workers, limit_per_query=args.limit, as_json=args.json, db_path=DB_PATH)
    elif args.command == "get-cluster":
        get_cluster(args.domain, max_workers=args.workers, as_json=args.json, summary=args.summary, db_path=DB_PATH)
    elif args.command == "benchmark-concurrency":
        benchmark_concurrency(num_queries=args.queries, max_workers=args.workers, db_path=DB_PATH)

    conn.close()


if __name__ == "__main__":
    main()
