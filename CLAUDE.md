# Crepidoma

Shared directives, agents and hooks come from the crepidoma plugin (this repo's own working copy, see `.claude/settings.json`). This file holds only what is specific to this repo.

## Project

- Foundation repo for Levia Labs pillar projects: Claude Code plugin, task namespaces, shared configs, templates, process ADRs.
- Public on GitHub: never commit local paths, emails, tokens or private repo names; `crepidoma-scrub` and gitleaks gate every commit.

## Stack

- Python 3.12+ stdlib for every script, uv, pytest, Task, pre-commit.

## Repo-specific rules

- New tool: follow `docs/contributing-tools.md` (script, test, task entry, receipt-sized output).
- Directives stay under 8,500 characters; the subagent harness under 1,500. Tests enforce both.
- Every folder keeps a README: run `task docs:readmes` after adding files; folder purposes live in `docs/folder-purposes.toml`.
- Ship changes through a PR, squash-merged; `main` is the only long-lived branch and what pillars track.
- Release: `task release -- X.Y.Z`, then `claude plugin marketplace update levia-labs`.

## Commands

- `task --list` shows every task; shared namespaces load from `taskfiles/`.
- `task validate` runs everything CI runs.
