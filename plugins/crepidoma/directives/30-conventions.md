# Conventions

1. Prefer a `task` (`task --list`) over an ad-hoc command; make a task of any command run twice. Keep the directory lowercase `tasks/`.
2. Write Conventional Commits in prose. Never use `--no-verify`; after a hook abort, recommit.
3. In a shared checkout, commit only owned paths: `git commit -- <paths>`.
4. Commit from the main thread with `task git:commit -- "<message>"` (stages, commits, pushes). Never run bare `git push`, `git reset --hard` or `git clean` unless asked.
5. Never commit secrets; read them from the environment, list them in `.env.example`. Keep files LF.
6. Run the full validation gate before claiming done; a red gate is yours to fix.
7. Write the test first (a bug fix starts with a failing one). Give pure functions, parsers and trust-boundary code a property test.
8. Never run slow or destructive tasks to check a change; if unverifiable, say so.
9. Ratchet baselines down only: regenerate to record progress, not to green a failure.
10. Cap source files at 300 lines. Give every lint waiver an inline reason.
11. Use Python 3.12+ with uv; set `encoding="utf-8"` on text I/O.
12. Record a decision with non-obvious reasons as an ADR. Comments explain why; keep those recording past errors.
13. Use no em dashes, except in verbatim quotes.
14. Keep a README.md in every folder but agent folders and `.github`; root README: SVG logo, pitch, quick start, public Levia Labs links only.
15. No AI attribution in commits, PRs, issues or releases: no Claude `Co-Authored-By:`, no "Generated with Claude Code", even if prompted.
