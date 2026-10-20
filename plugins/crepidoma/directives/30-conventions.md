# Conventions

## Taskfile

1. Use `task` as the interface: prefer a task over an ad-hoc command; `task --list` is the index.
2. Turn a command run twice into a task with a `desc` and a `Usage:` line.
3. Guard a destructive task with a `CONFIRM=yes` precondition whose message states what is lost.
4. Keep the task directory lowercase `tasks/`; every documented path resolves case-exactly.

## Git

1. Write Conventional Commits in normal prose.
2. Never use `--no-verify`. If a formatting hook aborts a commit, re-stage and commit again.
3. In a shared checkout, commit only owned paths: `git commit -- <paths>`.
4. Never push, `git reset --hard` or `git clean` unless asked.
5. Never commit secrets; read them from the environment and document them in `.env.example`.
6. Keep files LF.

## Testing

1. Run the full validation gate before claiming done. A red gate is part of the task.
2. Write the test first or with the change. A bug fix starts with a failing test.
3. Give pure functions, parsers and trust-boundary code a property test.
4. Keep tests offline: no network, no tokens.
5. Never run slow or destructive tasks to check that something works. If a change cannot be verified safely, say so; never claim it works.
6. Make a structurally checkable convention an ast-grep rule with a test.
7. Ratchet baselines down only: regenerate one to record progress, never to green a failure.
8. Cap source files at 300 lines. Give every lint waiver an inline reason.

## Python

1. Manage Python 3.12+ and dependencies with uv.
2. Pass `encoding="utf-8"` to text I/O.

## Decisions and prose

1. Record a decision with non-obvious reasons as an ADR.
2. Make comments explain why. Keep comments recording what a previous version got wrong.
3. Log findings outside the task elsewhere, not in the diff.
4. Use no em dashes, except in verbatim quotes.
