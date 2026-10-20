# 0003. Python dependencies and dev tools are locked with uv

## Status

Accepted, 2026-10-20. Supersedes the per-pillar ADRs on this topic.

## Context

An unpinned requirements list lets two builds a month apart install different software, so
neither an environment nor an image can be reproduced. Linters installed globally carry no
pin and a PATH that depends on the shell, so two machines can disagree about whether a gate
passed. The test runner, property testing, coverage and the type checker need one shared
environment, which isolated per-tool installs cannot give.

Pinning by hand drifts. `pip freeze` pins the resolution but loses the line between direct and
transitive dependencies. `pip-tools` adds a third tool to reach what uv reaches alone, and uv
resolves a typical dependency set in about a second.

## Decision

1. `pyproject.toml` declares dependencies, `uv.lock` resolves them, and uv does both.
   `uv.lock` is committed. This holds for every Python project, however small.
2. Dev tools live in a `dev` dependency group: test runner, property testing, coverage, type
   checker, ast-grep, linters, formatters, and every scanner published on PyPI. No dev tool
   comes from a global install.
3. Every task calls `uv run --locked`. Environments are created with `uv sync --locked`, and
   images install with `uv sync --locked --no-dev`. `--frozen` is not used: it installs from
   the lock without checking it, so a stale lock passes unnoticed.
4. A change to dependencies or to the `dev` group runs `uv lock` and commits the new lock in
   the same change.
5. No task depends on an activated virtualenv.
6. The type checker is basedpyright from the `dev` group, for its native baseline file that
   drops entries as they are fixed. mypy and ty are not used.
7. Each tool version is pinned in exactly one place. Linters already in `uv.lock` run as local
   hooks that call their task, not from a second hook repository with its own pin. A tool not
   on PyPI is pinned by version in its install command.
8. Tool configuration lives in `pyproject.toml` rather than per-tool dotfiles. Shared configs
   that Crepidoma ships under `.crepidoma/configs` are referenced, not copied.
9. uv is a prerequisite. The setup task installs it, and CI installs it with the pinned uv
   setup action.

## Consequences

1. `uv sync --locked` produces the same environment on every machine and in CI, and a lock
   that does not match `pyproject.toml` fails before anything installs.
2. Dependencies and tool configuration sit in one file instead of requirements files and
   several dotfiles.
3. The lock is one more file to keep current; `--locked` enforces that by failing.
4. `pyproject.toml` may build nothing and serve only as a dependency manifest.
5. The virtualenv grows, by about 120 MB for the Node runtime the type checker ships with.
6. Projects on pip with requirements files, or with a type checker installed through npm,
   migrate to this layout.
