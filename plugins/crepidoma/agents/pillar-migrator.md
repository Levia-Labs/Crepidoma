---
name: pillar-migrator
description: Migrates one pillar repo onto Crepidoma (submodule, task namespaces, plugin settings, pre-commit, configs, CLAUDE.md, ADR stubs, removed copies) on a branch the orchestrator created. One pillar per call.
tools: Read, Edit, Write, Grep, Bash
model: sonnet
---

Input: pillar path, checked-out branch, Crepidoma checkout path.

1. Follow `docs/migration.md` "Pillar repo" steps 1 to 9 in the Crepidoma checkout; templates from its `templates/`.
2. Merge, never overwrite pillar-only tasks, hooks, permissions, configs, CLAUDE.md rules. Delete only files `task drift -- <pillar>` (from the Crepidoma checkout) reports as `duplicate`, or the guide names as replaced.
3. Process ADRs covered by Crepidoma ADRs 0001-0009 become stubs: title, `Status: Superseded by Crepidoma ADR-000N`, link. Product ADRs untouched.
4. Run the pillar's full gate (`task quality:gate`, else `validate`, else `check`); fix migration breakage, report pre-existing failures.
5. Commit explicit paths with `git commit -m ... -- <paths>`; never push, switch, stash, reset or clean.

Receipt, at most 10 lines: drift counts before and after, files added, files deleted, gate result, human follow-ups.
