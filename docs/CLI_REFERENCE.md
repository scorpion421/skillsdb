# SkillsDB: Complete CLI Command Reference

This document provides a comprehensive command reference for all `skillsdb` CLI capabilities across discovery, episodic memory, guardrails, MCP, and Gitea integration.

---

## 1. Skill Discovery & Micro-Skills Retrieval

```powershell
# Auto-suggest matching skills for a task (with multilingual synonym expansion)
skillsdb suggest "mehrsprachige Flutter App bauen"
skillsdb suggest "BigQuery SQL pipeline optimization" --json

# Micro-skills: inspect outline and section token breakdown (~80 tokens)
skillsdb get-skill flutter-fix-layout-issues --summary

# Micro-skills: retrieve only a targeted section (~150 tokens, saving 85% context)
skillsdb get-skill flutter-fix-layout-issues --section "Fixing RenderFlex Overflow"

# Full-text search across all rules and 120 skills
skillsdb search "credentials dpapi"

# Retrieve full skill instructions
skillsdb get-skill admin-elevation

# Export a skill directly into a project repository (.agents/skills/<name>/SKILL.md)
skillsdb export-skill flutter-apply-architecture-best-practices .
```

---

## 2. High-Concurrency & Parallel Retrieval (Gemini Ultra)

```powershell
# View active model profile and concurrency settings
skillsdb profile

# Lock in your account pricing tier (ultra, standard, lean, local, offline)
skillsdb profile set ultra
skillsdb profile set local
skillsdb profile set offline

# Reset to automatic transcript/model detection
skillsdb profile auto

# Batch fetch multiple skills concurrently in 1 turn (up to 16 parallel threads)
skillsdb get-skills flutter-apply-architecture-best-practices flutter-add-widget-test --summary
skillsdb get-skills bigquery-sql dataform-bigquery --workers 8

# Prefetch an entire pre-indexed domain cluster concurrently
# Supported clusters: flutter, android, data, firebase, web, admin, security
skillsdb get-cluster flutter --summary
skillsdb get-cluster data --json
skillsdb get-cluster firebase --workers 16

# Execute multiple full-text search queries concurrently across 120+ skills
skillsdb search-multi "bigquery optimization" "firebase auth" "docker container"
skillsdb search-multi "hot reload" "widget test" --limit 3 --json

# Benchmark sequential vs. parallel multi-threaded retrieval throughput
skillsdb benchmark-concurrency --queries 20 --workers 16
```

---

## 3. Episodic Project Memory & Task State Machine (.agents/memory.db)

```powershell
# Retrieve recent project context (active tasks, decisions + latest milestone, ~150 tokens)
skillsdb mem-get-context

# Task State Machine: Add tasks with priority and status (pending, in_progress, completed, blocked)
skillsdb mem-task-add "Refactor database engine" --priority critical --status in_progress
skillsdb mem-task-add "Write comprehensive unit tests" --priority high

# View project task board (filtered or all)
skillsdb mem-task-list
skillsdb mem-task-list --status in_progress

# Update task status, priority, or details
skillsdb mem-task-update 1 --status completed
skillsdb mem-task-update 2 --priority critical

# Clear completed tasks from task board
skillsdb mem-task-clear

# Autonomous Context Compaction: Consolidate active session state & vacuum memory.db
skillsdb mem-compact --summary "Completed v3.5 Gitea integration" --next-steps "Deploy release"

# Save an architectural decision
skillsdb mem-save-decision "API Gateway" "Use HTTPS port 5001 with JWT auth" --category architecture

# Save a session milestone snapshot (automatically creates Git commit and pushes to Gitea)
skillsdb mem-save-snapshot "Refactored database pooling to WAL" --next-steps "Add unit tests"
skillsdb mem-save-snapshot "WIP local experiment" --no-git
skillsdb mem-save-snapshot "Local commit without remote push" --no-push

# Save a key-value configuration fact
skillsdb mem-save-fact "DB_POOL_MAX" "16"

# Full-text search within project memory
skillsdb mem-search "JWT"

# Prune deleted conversation snapshots and vacuum project database
skillsdb mem-prune --max-snapshots 10 --max-age 30
```

---

## 4. Guardrails, Agent Handoffs & Memory Reconciliation (OpenAI Fusion)

```powershell
# Check text or files against active formatting and credential guardrails
skillsdb guardrail check "Sample text to validate"
skillsdb guardrail check path/to/file.py --fix
skillsdb guardrail check --staged --strict

# Verify task execution with automated tests before completing
skillsdb guardrail verify-task 1 --command "pytest tests/"

# Initiate structured agent handoff with scoped context variables
skillsdb handoff create "security_auditor" "Audit auth flow" --context '{"scope": "jwt"}'
skillsdb handoff list
skillsdb handoff update 1 completed

# Fact reconciliation and tombstoning
skillsdb mem-reconcile "PORT" "8080"
skillsdb mem-deprecate-fact "LEGACY_ENDPOINT"
skillsdb mem-fact-history "PORT"
```

---

## 5. Native MCP Server, Codestral FIM Slicing & Agent Templates (Mistral Fusion)

```powershell
# Launch native JSON-RPC 2.0 stdio MCP server for Antigravity, Cursor, Continue.dev
skillsdb mcp-serve

# Surgical Fill-in-the-Middle (FIM) context slicing around lines or symbols
skillsdb fim slice path/to/file.py --line 45 --window 15
skillsdb fim slice path/to/file.py --symbol calculate_metrics --window 20

# Reusable Agent Templates Catalog (Mistral Agents API pattern)
skillsdb agent list
skillsdb agent get lead_architect
skillsdb agent register custom_dev --role "Backend Developer" --prompt "You write clean APIs." --skills "api-design"
```

---

## 6. Gitea Server Integration & Autonomous Code Memory (v3.5)

```powershell
# Check Gitea connection, server version, and project repository binding
skillsdb gitea status

# Initialize Git workspace, auto-create repository on local Gitea, and set origin
skillsdb gitea init [repo_name] [--description "My project description"] [--public]

# Directly stage changes, commit, and push to Gitea origin
skillsdb gitea sync "Refactor database query optimization"
skillsdb gitea sync --no-push

# Milestone snapshotting with automatic Git commit & Gitea push
skillsdb mem-save-snapshot "Completed feature milestone" --next-steps "Write tests"
```

---

## 7. Health Diagnostics, UTF-8 & Non-Destructive Updates

```powershell
# Run system diagnostics (DB integrity, concurrency engine, PATH, hooks, UTF-8)
skillsdb doctor

# View database statistics and measured token/cost savings
skillsdb stats
skillsdb stats --savings

# Check for updates on GitHub / local release server
skillsdb check-update

# Safely update SkillsDB to the latest release (zero data loss via differential merge)
skillsdb update
skillsdb update --force

# Configure Antigravity to run natively with UTF-8 process code page on Windows
skillsdb fix-utf8
skillsdb fix-utf8 --check
```
