---
name: docs-sweep
description: Use when asked to refresh a repo's documentation, ADRs, CLAUDE.md and other Markdown so they match the current code, to rebuild the graphify index, or to plan further token savings. Runs the read, update, index and plan passes through cheap tools and Haiku agents.
---

# Docs sweep

Keeps every Markdown file true to the code, short, and cheap to load. The main thread
orchestrates on Opus; it never reads the documents itself.

## Passes

1. **Finish lanes.** Wait for running subagents to finish and retire them before starting.
2. **Inventory.** List every `*.md` (CLAUDE.md, README, `docs/`, `docs/adr/`, `.claude/`) with
   `git ls-files '*.md'` and its size via `digest`. No full reads in the main thread.
3. **Check against code.** Per file, dispatch `scout` (Haiku) to list claims that no longer match
   the code: dead paths, renamed tasks, removed features, stale numbers. Receipt: `file:line | claim
| truth`, at most 10 lines.
4. **Update and simplify.** Per file with findings, dispatch a Sonnet agent (`docs-syncer`) to fix
   the claims, cut repetition and content duplicated from Crepidoma directives, and keep numbered
   lists. ADRs change only by Status line or a dated update note.
5. **Index.** Run graphify twice: the local AST pass first (`graphify update . --force`), then the
   LLM pass on Haiku for docs and semantic edges. Query the graph afterwards; never read
   `GRAPH_REPORT.md` whole.
6. **Token plan.** From session history and the refreshed index, list the repeated reads, large
   outputs and hand-written results that cost the most; propose one tool, task or skill per item,
   with its expected saving. Write the plan to `docs/` and confirm before building it.
7. **Gates.** Run the project's full validation gate; commit with explicit paths.

## Models

1. Main thread: Opus (`claude-opus-5-5`), orchestration only.
2. Edits and reviews: Sonnet (`claude-sonnet-5-5`).
3. Reading, checking claims and graphify LLM indexing: Haiku (`claude-haiku-5-5`).
