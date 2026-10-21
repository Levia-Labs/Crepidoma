# 0002. Local quality gates run in two tiers

## Status

Accepted, 2026-10-20. Supersedes the per-pillar ADRs on this topic.

## Context

An agent that verifies a change by reading code pays tokens for every file and still misses
what a tool catches in milliseconds. Verification belongs in tools that run on the local
machine and print compact output: one line naming the file and line, or the smallest input
that fails.

The agent Stop hook runs a gate after every turn that edits files, so every check in that gate
is paid on every turn. Tests under coverage, history scans and dependency audits cost tens of
seconds, and a networked check fails or stalls whenever the network is down or the host
resolves only whitelisted names. Leaving those checks out of every gate leaves them unrun, and
a gate nobody runs is documentation.

## Decision

1. Every check is a task. A git hook entry, a Stop hook step, a CI step and a manual run are
   the same command.
2. `task check` is the fast tier. It is offline, takes seconds, and runs cheapest first,
   fail-fast: the task-tree check, linters and formatters in check mode, ast-grep project
   rules, structure and doc gates, the type checker, the test suite with property tests at a
   low example count, and a secret scan of the working tree.
3. `task validate` is the full tier and is the same as CI. It runs everything in `check`, with
   the test suite run once under branch coverage instead of plain, and adds the coverage
   ratchet, property tests at a high example count, the ast-grep rule tests, a secret scan of
   the whole git history, the static-analysis and workflow scanners, dependency audits, and
   the build where the project has one.
4. The agent Stop hook runs `task check` after every turn that changed the working tree,
   documentation-only turns included.
5. The commit hook runs the fast-tier checks over the staged files. The type checker, the test
   suite and the ast-grep rules run over the whole project whenever a matching file is staged,
   because a change in one file can break another.
6. The push hook and CI run `task validate`.
7. The fast tier never touches the network. In the full tier only dependency audits may reach
   the network, and only to fetch advisory databases. Scanners run the rules committed in the
   repository, with registry rule packs, metrics and version checks off.
8. A tool missing on the editing host may skip in `task check` with one line naming it. In
   `task validate`, the push hook and CI a missing tool fails.
9. Type errors, coverage gaps and other findings that predate a gate are baselined. Baselines
   and coverage thresholds only move toward stricter; a change that worsens one fails.
10. A waiver (an ignore-file entry, an inline disable) carries its reason inline. A
    dependency-advisory waiver also carries an expiry date. ast-grep rules carry no file
    exceptions; allowed names go in the rule's allow pattern.
11. Crepidoma ships the gates. Shared commit and push gates are pre-commit hooks from
    `github.com/Levia-Labs/Crepidoma`, pinned by `rev` and updated with
    `pre-commit autoupdate`. Shared tool configs live under `.crepidoma/configs`. A project
    references both and does not copy them.

## Consequences

1. A convention written as an ast-grep rule or a test is checked on every turn at no token
   cost, instead of only when someone remembers to read for it.
2. An agent turn can end with coverage dropped, a secret in history or a new advisory. The
   push hook and CI catch it, later than the turn that caused it.
3. There are two task names to learn. `task validate` keeps its meaning of "everything", so
   the rule to run it before calling a change done still holds.
4. Every edited turn pays for the fast tier. Keeping it to seconds is a standing constraint: a
   check that slows it moves to the full tier.
5. Baseline files are reviewed like code, and a baseline that grows needs a stated reason.
6. On a new machine the first runs download and build the pinned tools; later runs hit the
   cache.
7. A single tier was rejected on cost and on network dependence. A changed-files test selector
   was rejected because a wrong mapping silently skips a test.
