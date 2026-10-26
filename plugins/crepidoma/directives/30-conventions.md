# Conventions

1. Prefer a `task` over an ad-hoc command; `task --list` is the index. Turn a command run twice into a task. Keep the directory lowercase `tasks/`.
2. Write Conventional Commits in normal prose. Never use `--no-verify`; after a hook abort, re-stage and recommit.
3. In a shared checkout, commit only owned paths: `git commit -- <paths>`.
4. Commit from the main thread with `task git:commit -- "<message>"` (stages all, commits, pushes). Never run bare `git push`, `git reset --hard` or `git clean` unless asked.
5. Never commit secrets; read them from the environment and document them in `.env.example`. Keep files LF.
6. Run the full validation gate before claiming done; a red gate is part of the task.
7. Write the test first or with the change; a bug fix starts with a failing test. Give pure functions, parsers and trust-boundary code a property test.
8. Never run slow or destructive tasks to check that something works; if a change cannot be verified safely, say so.
9. Ratchet baselines down only: regenerate to record progress, never to green a failure.
10. Cap source files at 300 lines. Give every lint waiver an inline reason.
11. Use Python 3.12+ with uv; pass `encoding="utf-8"` to text I/O.
12. Record a decision with non-obvious reasons as an ADR. Make comments explain why; keep ones recording past errors.
13. Use no em dashes, except in verbatim quotes.
14. Keep a README.md in every folder except agent folders and `.github`. Keep the root README short: SVG logo, one-line pitch, quick start, links to public Levia Labs repos only.
