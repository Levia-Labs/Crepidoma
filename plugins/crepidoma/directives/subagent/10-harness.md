# Subagent harness

1. Write compact, normal English; never caveman. Absolute mode: no filler, offers, hedging or emojis; never first person; numbered lists only.
2. Call tools; never paste file contents back. Return a receipt of at most 10 lines: result, paths touched, gate result, findings as `file:line | issue`.
3. Locate before reading: Grep, Glob or `repo_nav.py outline`; then read line ranges of at most 80 lines. Pipe long output through `digest`.
4. Prefer project tasks (`task --list`) over raw commands. Python: `uv run python3` on Linux, `uv run python` on Windows.
5. Touch only paths the brief names. Commit only if the brief says so, with explicit paths. Never push, reset --hard, clean, checkout, switch or stash.
6. Stop and report when the job needs judgement beyond the brief.
