# 0009. Model tiers, shell and subagent harness

## Status

Accepted, 2026-10-20.

## Context

Subagents loaded the full main-thread directives and caveman on every start. Each spawn paid
that token cost again, and the output style meant for the main thread bloated short
lookups. Model choice was per-session and drifted. PowerShell and Bash mixed in one session
produced quoting failures and chained commands that hid which step failed.

## Decision

1. The main thread runs Opus, pinned in committed settings.
2. Subagents default to Sonnet through `CLAUDE_CODE_SUBAGENT_MODEL=sonnet`; an agent's
   frontmatter `model` overrides it.
3. A Haiku scout handles grep, read and small lookups. graphify LLM indexing also runs on
   Haiku.
4. A PreToolUse hook enforces the tiers and blocks mismatches.
5. caveman applies to the main thread only.
6. Subagents receive a compact harness through a SubagentStart hook instead of the main
   directives.
7. Absolute mode applies to every thread.
8. Bash is the only shell; PowerShell is denied.
9. One command per call; no chaining.
10. Scripts call the interpreter through the `PY` var: `python3` on Linux, `python` on Windows.
11. Commits go through `task git:commit` (add, commit, push).
12. Sessions stop at 95 percent usage.

## Consequences

1. Subagent start cost drops to the compact harness; the main directives and caveman are
   not reloaded per spawn.
2. Sonnet and Haiku handle bulk work at lower cost; Opus is reserved for the main thread.
3. A subagent needing Opus must declare it in frontmatter.
4. The hook can block legitimate work when a model mismatch is intentional; the override
   is a committed settings change.
5. Single commands cost more tool calls but give one failure per call.
6. `task git:commit` pushes on every commit, so unreviewed commits reach the remote.
7. The 95 percent ceiling can end a task midway; work must be resumable.
