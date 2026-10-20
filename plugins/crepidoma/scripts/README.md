# Scripts

- Stdlib tools behind hooks and task namespaces; contract in docs/contributing-tools.md.

## Contents

<!-- contents:start -->

- [`lint/`](lint/README.md) - Folder.
- [`agent_pool.py`](agent_pool.py) - Subagent pool: list finished agents of the current session and steer dispatch to reuse them.
- [`allow_tasks.py`](allow_tasks.py) - Keep .claude/settings.json permissions consistent with the Taskfile interface.
- [`budget.py`](budget.py) - Claude usage windows against a ceiling: show, gate, wait.
- [`ci_runs.py`](ci_runs.py) - Watch a CI run and read its failing-job errors, for this or another GitHub repo.
- [`digest.py`](digest.py) - Qualify long text before it reaches the main thread (stdlib only).
- [`docs_gate.py`](docs_gate.py) - Docs consistency gate: broken links and README file lists, with a ratchet baseline.
- [`gate_runner.py`](gate_runner.py) - Run gates quietly: one line per task, failure excerpt only on failure.
- [`git_after_merge.py`](git_after_merge.py) - Reset a repo to its default branch after a PR merge and print one receipt line.
- [`history.py`](history.py) - Find repeated ad-hoc work in Claude Code history that should become a tool (stdlib only).
- [`hooks.py`](hooks.py) - Claude Code hooks: quality gates at the end of a turn and the agent dispatch policy.
- [`inject_directives.py`](inject_directives.py) - SessionStart and SubagentStart hook: emit Crepidoma directives as additional context.
- [`lanes.py`](lanes.py) - List and reset subagent lanes, and write a save-state note for a later session.
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
