# Central Database Rules Directive

All system rules, coding standards, administrative credentials, and skills are maintained in the central database:
`~/.gemini/database/customizations.db`

The agent must always adhere to the active global rules registered in the database with HIGHEST PRIORITY:

1. **Global Output Formatting Invariant (Strict Enforcement Across ALL Operations)**:
   - **No Em-Dashes or En-Dashes**: Under no circumstances output em-dashes (Unicode U+2014) or en-dashes (Unicode U+2013). This applies universally to ALL output: chat responses, markdown documents, code comments, commit messages, and artifacts. Always use standard ASCII hyphens (`-`), colons (`:`), or parentheses instead.
   - **No Emojis**: Under no circumstances output emojis, smileys, or decorative Unicode symbols.

2. **Conversational Communication**:
   - Always use informal German ("Du", never "Sie") when conversing with the user.
   - Use natural German spelling INCLUDING umlauts (ä, ö, ü, ß). Never replace umlauts with ae, oe, ue in regular conversation text.

3. **Coding & Scripting Standards**:
   - All code, comments, console outputs, dialogs, and commit messages strictly in grammatically correct English (ASCII only).
   - Strictly no VBScript (`.vbs`, `cscript`, `wscript`). Always use native PowerShell or standard APIs.

4. **Admin Elevation**:
   - Use DPAPI credentials for the current user's .adm account (`<DOMAIN>\<USERNAME>.adm`) without interactive UAC prompts.

5. **Token Efficiency & Context Hygiene**:
   - Strict context hygiene (slice file reads with StartLine/EndLine, compact command outputs like `git status -s`, subagent isolation, no verbose fluff or restatements).

6. **Project Memory**:
   - In project workspaces, use `.agents/memory.db` for multi-step tasks, architectural work, or extended conversations (omit for trivial one-off queries to save tokens). When handling non-trivial tasks: run `skillsdb mem-get-context` at task start to load context (auto-initializes if new), and record milestone snapshots via `skillsdb mem-save-snapshot "<summary>"` upon completing significant changes or sessions.

To inspect or search detailed rules and workflow skills on demand, use the `customizations-db` skill or run:
`skillsdb get-active-rules` (or `python "$env:USERPROFILE\.gemini\database\db_manager.py" get-active-rules`)
