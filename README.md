# SkillsDB: Centralized Customizations & Token-Efficient Knowledge Engine for Google Antigravity

[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-blue.svg)](https://github.com/scorpion421/skillsdb)
[![Python](https://img.shields.io/badge/python-3.10%2B-brightgreen.svg)](https://www.python.org/)
[![PowerShell](https://img.shields.io/badge/powershell-5.1%2B%20%7C%207%2B-blue.svg)](https://github.com/PowerShell/PowerShell)
[![SQLite](https://img.shields.io/badge/database-SQLite3%20FTS5%20%7C%20WAL-lightgrey.svg)](https://www.sqlite.org/)
[![Antigravity](https://img.shields.io/badge/compatible-Google%20Antigravity%202.0-orange.svg)](https://deepmind.google/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**SkillsDB** is a high-performance knowledge indexing, retrieval, and episodic memory architecture designed for Google Antigravity AI agents. It eliminates static prompt bloat by decoupling enterprise rules and domain skills into an embedded, on-demand SQLite FTS5 database.

---

## What is SkillsDB and Why Do Beginners Need It?

If you are just getting started with coding or using AI assistants like Google Antigravity, all the technical discussions about *tokens*, *SQLite databases*, and *system prompts* might sound intimidating.

Here is the simple, real-world explanation:

### The Backpack Metaphor

Imagine hiring a smart assistant to help you learn programming or build your first project:
* **Without SkillsDB**: Every time you ask a simple question like *"How do I change this button color?"*, your assistant is forced to pack **120 heavy encyclopedias** into their backpack (covering mobile frameworks, data science libraries, cloud servers, and corporate rules) before answering you.
  * Result: Your assistant moves slowly, gets confused by irrelevant information, and quickly exhausts your daily AI usage limit.
* **With SkillsDB**: Your assistant carries only a lightweight notebook. When you ask about button styling, the assistant looks up *only* the single page on CSS from a local digital library in milliseconds, answers you immediately, and puts the book back.

---

### How It Works: Traditional Loading vs. SkillsDB

```mermaid
flowchart TD
    subgraph OldWay ["The Old Way (Without SkillsDB)"]
        direction TB
        Q1["You: 'How do I center a button in CSS?'"] --> Step1["AI Assistant must load EVERYTHING into memory:"]
        Step1 --> Books["40 Biology databases\n25 Cloud big-data tools\n23 Mobile app frameworks\nDozens of complex rules"]
        Books --> Burn["15,000 tokens burned on startup\n(Like paying for 50 pages of text just to say 'Hello')"]
        Burn --> Slow["Slow answers & quick quota exhaustion"]
    end

    subgraph NewWay ["The SkillsDB Way (Automatic & Lean)"]
        direction TB
        Q2["You: 'How do I center a button in CSS?'"] --> Step2["AI Assistant starts super light (~380 tokens)"]
        Step2 --> Search["Quickly checks its local SkillsDB library:"]
        Search --> Exact["Grabs ONLY the CSS layout skill in milliseconds"]
        Exact --> Fast["Instant answer, 97% cheaper, remembers your project!"]
    end
```

---

### 4 Big Benefits for Beginners

1. **You Won't Run Out of AI Usage Quota**:
   Every word an AI reads or writes consumes "tokens" (like fuel). By reducing startup waste by **97.4%**, you can ask dozens of questions and experiment freely without hitting *"Usage limit reached"* warnings.
2. **Clearer, Higher-Quality Answers**:
   When the AI is not distracted by 100 tools it does not need for your task, its answers are more focused, concise, and easier to understand.
3. **Automatic Project Memory (No Repeating Yourself!)**:
   Normally, when you start a new chat tomorrow, the AI forgets everything you built today. SkillsDB automatically remembers your project's decisions and milestones, so you never have to re-explain your whole project from scratch.
4. **Zero Extra Work for You**:
   You do not need to learn any database commands or manage files. You talk to your AI assistant naturally, and SkillsDB works invisibly in the background.

---

## Technical Deep-Dive: The "Prompt Bloat" Crisis in AI Coding Assistants

By default, Google Antigravity discovers and injects every plugin found in `~/.gemini/config/plugins` into the agent's global system prompt on session startup. When developers install standard domain plugins (such as `science`, `flutter`, `data-agent-kit`, `firebase`, etc.), the cumulative token overhead triggers a critical warning:

```text
Customization token budget exceeded. Large customizations will be truncated.
```

### The Real Cost of Static Injection:
* **Over 15,000 tokens burned** on every single user prompt before work even begins.
* **Context Dilution**: The "Lost-in-the-Middle" phenomenon degrades model reasoning when overwhelmed by dozens of irrelevant tools.
* **Excessive Latency & Cost**: Unnecessary token transmission on every turn consumes API quotas and slows down response times.

---

## The Solution: On-Demand Decoupling (-97.4% Overhead)

SkillsDB replaces static prompt dumping with an indexed **SQLite knowledge engine** backed by SQLite FTS5 (Full-Text Search) and WAL (Write-Ahead Logging) mode. The agent starts with a lightweight directive (~380 tokens) and fetches domain skills and rules only when the user's task requires them.

| Metric | Traditional Static Loading | SkillsDB Architecture | Improvement |
| :--- | :--- | :--- | :--- |
| **Startup Prompt Overhead** | ~14,813 tokens | **~382 tokens** | **-97.4% reduction** |
| **Available Knowledge Base** | 120 skills (choking context) | **120 skills** (FTS5 indexed) | **100% capacity preserved** |
| **Multi-Turn Step Efficiency** | 15k tokens per round-trip | **~380 tokens per round-trip** | **~170k+ tokens saved / 12 steps** |
| **Scalability Limit** | ~10-15 plugins maximum | **10,000+ skills effortlessly** | **Infinite scalability** |

---

## Architecture Overview

```mermaid
flowchart TD
    subgraph Antigravity ["Google Antigravity Runtime"]
        Agent["Antigravity Agent (LLM)"]
        Directive["Global Directive (AGENTS.md)\n~382 tokens"]
    end

    subgraph CentralEngine ["SkillsDB Central Knowledge Engine"]
        CLI["skillsdb CLI (PATH)"]
        CentralDB[("customizations.db\nSQLite FTS5 + WAL")]
        PluginArchive["plugins_archive/\n(120+ domain skills)"]
    end

    subgraph ProjectWorkspace ["Project Workspace (.agents/)"]
        MemDB[("memory.db\nEpisodic Project Memory")]
        Decisions["Architectural Decisions"]
        Snapshots["Session Milestones"]
    end

    Directive -->|"Guides agent autonomously"| Agent
    Agent -->|"On-demand lookup (suggest / get-skill)"| CLI
    CLI <-->|"Sub-millisecond query"| CentralDB
    CentralDB <-->|"Sync & indexing"| PluginArchive
    Agent -->|"Automated session memory"| MemDB
    MemDB --> Decisions
    MemDB --> Snapshots
```

---

## Core Philosophy: Zero Cognitive Load

The core design principle of SkillsDB is **complete transparency**:

1. **Autonomous Knowledge Retrieval**:
   The user asks a question in plain natural language (*"Fix this layout overflow in Flutter"*). The agent detects the domain, queries `skillsdb suggest` in milliseconds, retrieves the relevant skill, and executes the solution.
2. **Effortless Workstation Deployment**:
   Provisioning a new machine takes one sentence to Antigravity: *"Please deploy Antigravity customizations from this repository"*.
3. **Continuous Autonomous Learning**:
   Telling the agent *"Remember this convention"* automatically persists it to the database via CLI in the background.

---

## Project-Level Episodic Memory (`.agents/memory.db`)

To prevent bloating the global database with project-specific trivia while still preserving architectural decisions across sessions, each project maintains an isolated episodic SQLite memory:

* **Autonomous Lifecycle**:
  * **Trivial Queries** (*"How does this regex work?"*): Memory is bypassed entirely (0 token overhead, no disk footprint).
  * **Non-Trivial Tasks** (Refactoring, features, long sessions): The agent runs `skillsdb mem-get-context` at task start and records progress snapshots via `skillsdb mem-save-snapshot` upon completion.
* **Zero Orphan Footprint**: Deleting a project folder deletes its memory database instantly.
* **Auto-Pruning (`mem-prune`)**: Automatically reconciles deleted Antigravity conversation IDs and reclaims disk space with incremental SQLite auto-vacuum.

---

## Quick Start & Installation

### Option 1: One-Command Deployment via Antigravity Agent
Simply clone the repository and tell your Antigravity agent:
> **"Please deploy Antigravity customizations from this repository"**

### Option 2: Automated Script Deployment

#### Windows (PowerShell):
```powershell
powershell -ExecutionPolicy Bypass -File .\deploy.ps1
```

#### Cross-Platform (Python):
```bash
python deploy.py
```

The script automatically:
1. Deploys `customizations.db` to `~/.gemini/database/`.
2. Installs the `skillsdb` CLI to `~/.gemini/antigravity/bin/` (in your system PATH).
3. Configures `customizations-db` as the sole active plugin in `~/.gemini/config/plugins/`.
4. Safely moves static legacy plugins to `~/.gemini/plugins_archive/` (completely eliminating prompt bloat and dormant MCP startup errors).

---

## CLI Reference Guide

The global `skillsdb` command is accessible from any terminal and working directory:

### 1. Rules & Skills
```powershell
# Display all active system rules
skillsdb get-active-rules

# Auto-suggest the best matching skills for a task
skillsdb suggest "Flutter widget layout overflow"

# Retrieve full instructions for a specific skill
skillsdb get-skill admin-elevation

# Micro-Skills: Inspect outline & section list (~80 tokens)
skillsdb get-skill flutter-fix-layout-issues --summary

# Micro-Skills: Load only a specific section (~150 tokens, saving 85% context)
skillsdb get-skill flutter-fix-layout-issues --section "Fixing RenderFlex Overflow"

# Autonomous Learning: Persist a learned rule globally into SQLite
skillsdb learn-rule "python-standards" "Python Guidelines" "Always use typing and dataclasses."

# Full-text search across all rules and 120 skills
skillsdb search "bigquery"

# Run system health diagnostics (DB integrity, PATH, hooks, git ignore)
skillsdb doctor

# View database statistics and measured token/cost savings
skillsdb stats

# Check for updates on GitHub (version comparison & changelog)
skillsdb check-update

# Safely update SkillsDB to latest release (zero data loss via differential merge)
skillsdb update
```

### 2. Project Memory (.agents/memory.db)
```powershell
# Retrieve recent project context (decisions + latest milestone, ~150 tokens)
skillsdb mem-get-context

# Save an architectural decision
skillsdb mem-save-decision "API HTTPS Port" "Use Port 5001 with JWT authentication"

# Save a session milestone snapshot
skillsdb mem-save-snapshot "Migrated authentication middleware" --next-steps "Write integration tests"

# Save a key-value configuration fact
skillsdb mem-save-fact "DB_HOST" "sql01.internal.local"

# Full-text search within project memory
skillsdb mem-search "JWT"

# Prune deleted conversations and vacuum database
skillsdb mem-prune
```

### 3. Database Management & Team Synchronization
```powershell
# Re-index all skills from global and archived plugins
skillsdb import-all

# Import any Markdown rule or skill file
skillsdb import-file "path/to/custom_skill.md"

# Push local database updates to network team share
skillsdb sync push

# Pull latest team database updates from network share
skillsdb sync pull
```

---

## Global System Rules Enforced

All Antigravity agents running with SkillsDB adhere to 5 core directives:

1. **Communication**: Informal German ("Du", never "Sie") when conversing with German-speaking users.
2. **Scripting Standards**: Professional English code, comments, and outputs; no emojis; no em-dashes or en-dashes; strictly no VBScript.
3. **Admin Elevation**: Seamless execution with elevated administrator privileges using encrypted Windows DPAPI credentials without interactive UAC prompts.
4. **Token Efficiency**: Strict context hygiene (line-sliced file views, bounded command outputs, subagent isolation for wide searches, concise responses).
5. **Project Memory**: Autonomous project continuity via `.agents/memory.db` for multi-step tasks; zero overhead on trivial questions.

---

## Project Structure

```text
SkillsDB/
├── .agents/                    # Project-level episodic memory (.agents/memory.db)
├── database/
│   ├── customizations.db       # Central SQLite database (120 skills, 7 rules, FTS5)
│   └── db_manager.py           # Core CLI engine and SQLite abstraction layer
├── plugin/
│   ├── plugin.json             # Antigravity plugin manifest
│   ├── rules/
│   │   └── AGENTS.md           # Minimal ~380-token system prompt directive
│   └── skills/
│       └── customizations-db/  # Customization DB interface skill
├── deploy.ps1                  # PowerShell automated deployment script (Windows)
├── deploy.py                   # Python automated deployment script (Cross-platform)
├── .gitignore                  # Git hygiene configuration
└── README.md                   # System documentation
```

---

## License

This project is licensed under the [MIT License](LICENSE).
