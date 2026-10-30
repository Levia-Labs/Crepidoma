# Scripts

- Stdlib tools behind hooks and task namespaces; contract in docs/contributing-tools.md.

## Contents

<!-- contents:start -->

- [`claude/`](claude/README.md) - Folder.
- [`lint/`](lint/README.md) - Folder.
- [`agent_pool.py`](agent_pool.py) - Subagent pool: list finished agents of the current session and steer dispatch to reuse them.
- [`allow_tasks.py`](allow_tasks.py) - Keep .claude/settings.json permissions consistent with the Taskfile interface.
- [`budget.py`](budget.py) - Claude usage windows against a ceiling: show, gate, wait.
- [`budget_auth.py`](budget_auth.py) - OAuth token for budget.py: the Claude credentials file, or the macOS login Keychain.
- [`budget_view.py`](budget_view.py) - Rendering for budget.py: spans, labels, the usage bar and tab-separated rows.
- [`ci_runs.py`](ci_runs.py) - Watch a CI run and read its failing-job errors, for this or another GitHub repo.
- [`digest.py`](digest.py) - Qualify long text before it reaches the main thread (stdlib only).
- [`digest_kinds.py`](digest_kinds.py) - Kind-aware digest bodies: Markdown headings, code definitions, log failures, head and tail.
- [`docs_gate.py`](docs_gate.py) - Docs consistency gate: broken links and README file lists, with a ratchet baseline.
- [`gate_runner.py`](gate_runner.py) - Run gates quietly: one line per task, failure excerpt only on failure.
- [`git_after_merge.py`](git_after_merge.py) - Reset a repo to its default branch after a PR merge and print one receipt line.
- [`history.py`](history.py) - Find repeated ad-hoc work in Claude Code history that should become a tool (stdlib only).
- [`hook_shebang.py`](hook_shebang.py) - Rewrite `#!/bin/sh` to `#!/usr/bin/env sh` in .git/hooks/*.legacy.
- [`hooks.py`](hooks.py) - Claude Code hooks: quality gates at the end of a turn and the agent dispatch policy.
- [`hooks_bash.py`](hooks_bash.py) - The git guard: refuses a subagent's push, working-tree discard or sweeping stage.
- [`hooks_bash_guards.py`](hooks_bash_guards.py) - Bash guards for every caller: stdin-reading interpreters, kill-by-name, raw commit.
- [`hooks_budget.py`](hooks_budget.py) - The usage allowance: a cached reading and the refusal when a window is at the ceiling.
- [`hooks_common.py`](hooks_common.py) - Shared by every hook module: the project root, hook state, the payload and a refusal.
- [`hooks_pre_tool.py`](hooks_pre_tool.py) - Agent dispatch policy and the lane ledger: PreToolUse, SubagentStart, SubagentStop.
- [`hooks_stop.py`](hooks_stop.py) - Quality gates: PostToolUse marks a gate dirty, Stop runs the dirty gates' tasks.
- [`inject_directives.py`](inject_directives.py) - SessionStart and SubagentStart hook: emit Crepidoma directives as additional context.
- [`lanes.py`](lanes.py) - List and reset subagent lanes, and write a save-state note for a later session.
- [`mine.py`](mine.py) - Mine every Claude Code project folder in one call (stdlib only).
- [`raw_read_guard.py`](raw_read_guard.py) - PreToolUse hook: keep raw file content out of the main Claude thread (stdlib only).
- [`repo_nav.py`](repo_nav.py) - Locate code without reading whole files: outline, section, tasks, diff.
- [`rtk_route.py`](rtk_route.py) - PreToolUse hook: route a command through `rtk` when a project filter matches it (stdlib only).
- [`spend.py`](spend.py) - Audit where Claude Code session transcripts spent tokens and money (stdlib only).
- [`spend_parse.py`](spend_parse.py) - Transcript parsing for spend.py (stdlib only): tool calls, result sizes, usage per run.
- [`spend_startup.py`](spend_startup.py) - `spend.py startup`: per-subagent startup cost (stdlib only). Not a command by itself.
- [`taskfile_lint.py`](taskfile_lint.py) - Lint Taskfiles against the taskfile-shell directive without a YAML library.
- [`todo.py`](todo.py) - List, show, add, update and drop entries of a repo-root TODO.md.
- [`usage_rate.py`](usage_rate.py) - Project allowance burn rate from recorded usage samples.

<!-- contents:end -->
