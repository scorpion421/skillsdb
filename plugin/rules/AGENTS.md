# Central Database Rules Directive

All system rules, coding standards, administrative credentials, and skills are maintained in the central database:
`~/.gemini/database/customizations.db`

The agent must always adhere to the active global rules registered in the database:
1. **Communication**: Always use informal German ("Du", never "Sie") when conversing with the user.
2. **Scripting**: English code, comments, output; no emojis; no em-dashes/en-dashes; strictly no VBScript.
3. **Admin Elevation**: Use DPAPI credentials for the current user's .adm account (`<DOMAIN>\<USERNAME>.adm`) without interactive UAC prompts.
4. **Token Efficiency**: Strict context hygiene (slice file reads, compact command outputs, subagent isolation, no verbose fluff).
5. **Project Memory**: In project workspaces, use `.agents/memory.db` for multi-step tasks, architectural work, or extended conversations (omit for trivial one-off queries to save tokens). When handling non-trivial tasks: run `skillsdb mem-get-context` at task start to load context (auto-initializes if new), and record milestone snapshots via `skillsdb mem-save-snapshot "<summary>"` upon completing significant changes or sessions.

To inspect or search detailed rules and workflow skills on demand, use the `customizations-db` skill or run:
`skillsdb get-active-rules` (or `python "$env:USERPROFILE\.gemini\database\db_manager.py" get-active-rules`)
