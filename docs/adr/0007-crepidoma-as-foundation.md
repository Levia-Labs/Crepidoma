# 0007. Crepidoma as the foundation for pillar projects

## Status

Accepted, 2026-10-20.

## Context

Pillar repos carried drifted copies of agents, hook scripts, Taskfiles, lint and security
configs, CLAUDE.md sections and process ADRs. No copy was identical to another. CLAUDE.md
cannot import URLs; Claude Code plugins cannot ship CLAUDE.md, permissions or statusLine.

## Decision

1. Claude assets ship as the `crepidoma` plugin from the `levia-labs` marketplace in this repo.
   Directives reach sessions through a SessionStart hook, capped at 10,000 characters.
2. Taskfiles and configs ship through a `.crepidoma` git submodule.
3. Commit gates ship as pre-commit hooks from this repo (`.pre-commit-hooks.yaml`).
4. Third-party plugins and skills are referenced in templates, never copied.
5. Hooks run project code (task gates, graphify, a budget script) only in projects whose
   committed `.claude/settings.json` enables `crepidoma`.
6. `tools/drift_check.py` reports pillar copies that should be deleted or reconciled.

## Consequences

1. A pillar adopts Crepidoma with three committed references and one install command per collaborator.
2. Changes land once, here, and reach pillars on plugin update, submodule bump or pre-commit autoupdate.
3. Every push here is public: scrub_check and gitleaks gate every commit and push.
4. Repo-specific rules stay in each pillar's CLAUDE.md.
