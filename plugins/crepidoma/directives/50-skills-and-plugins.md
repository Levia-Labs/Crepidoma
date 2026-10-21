# Skills and plugins

1. Keep local skills in `.claude/skills/`, shared plugins in `.claude/settings.json`; list both in `.claude/README.md`.
2. Apply the matching process skill before acting: brainstorming (creative work), frontend design (new UI), feature development (multi-file feature), systematic debugging and TDD (bug), verification before completion (done claims), code review (diff or PR).
3. Run a humanizing skill over prose others read.
4. Use terse output modes in chat only; write code, comments, commits, docs and security warnings in normal English.
5. On `/graphify`, use the installed graphify skill first. Query a shipped graph only through project tasks, before grep for cross-file questions.
6. Never read the graphify-out graph report whole; run a scoped query.
7. After code changes, refresh the graph AST-only; run model extraction only after doc changes, on the smallest model.
