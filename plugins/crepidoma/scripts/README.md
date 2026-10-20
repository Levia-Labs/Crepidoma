# Scripts

- Stdlib tools behind hooks and task namespaces; contract in docs/contributing-tools.md.

## Contents

<!-- contents:start -->

- [`allow_tasks.py`](allow_tasks.py) - Keep .claude/settings.json permissions consistent with the Taskfile interface.
- [`budget.py`](budget.py) - Claude usage windows against a ceiling: show, gate, wait.
- [`digest.py`](digest.py) - Qualify long text before it reaches the main thread (stdlib only).
- [`docs_gate.py`](docs_gate.py) - Docs consistency gate: broken links and README file lists, with a ratchet baseline.
- [`gate_runner.py`](gate_runner.py) - Run gates quietly: one line per task, failure excerpt only on failure.
- [`history.py`](history.py) - Find repeated ad-hoc work in Claude Code history that should become a tool (stdlib only).
- [`hooks.py`](hooks.py) - Claude Code hooks: quality gates at the end of a turn and the agent dispatch policy.
- [`inject_directives.py`](inject_directives.py) - SessionStart and SubagentStart hook: emit Crepidoma directives as additional context.
- [`lanes.py`](lanes.py) - List and reset subagent lanes, and write a save-state note for a later session.
- [`raw_read_guard.py`](raw_read_guard.py) - PreToolUse hook: keep raw file content out of the main Claude thread (stdlib only).
- [`repo_nav.py`](repo_nav.py) - Locate code without reading whole files: outline, section, tasks, diff.
- [`spend.py`](spend.py) - Audit where Claude Code session transcripts spent tokens and money (stdlib only).
- [`taskfile_lint.py`](taskfile_lint.py) - Lint Taskfiles against the taskfile-shell directive without a YAML library.
- [`todo.py`](todo.py) - List, show, add, update and drop entries of a repo-root TODO.md.
- [`usage_rate.py`](usage_rate.py) - Project allowance burn rate from recorded usage samples.

<!-- contents:end -->
