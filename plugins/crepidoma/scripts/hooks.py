#!/usr/bin/env python3
"""Claude Code hooks: quality gates at the end of a turn and the agent dispatch policy.

One CLI, one subcommand per hook event; each reads the hook's JSON payload on stdin.

  post-tool-use    after Edit/Write/MultiEdit - marks a gate dirty when the file is in scope
  pre-tool-use     before Agent/Task - refuses a catch-all agent type, a model other than
                   sonnet or haiku, a seventh concurrent agent, or any agent while a usage
                   window is at the ceiling
  pre-bash         before Bash, subagents only - refuses a push or a working-tree discard
  subagent-start   a dispatched agent began - its reservation becomes a running lane
  subagent-stop    an agent finished - its lane is freed
  stop             end of a turn - runs the dirty gates' tasks, blocks on failure

Keeping raw file content out of the main thread is raw_read_guard.py's job, not this file's.

Paths are computed from the project directory (CLAUDE_PROJECT_DIR, else the working
directory). Markers, the lane ledger and the usage cache live under .git, never committed.

Contract: the exit code is always 0. A refusal is a `permissionDecision: deny` object and a
Stop block a `decision: block` object, both JSON on stdout. Malformed or empty stdin and any
internal error exit 0 with no output: the hooks fail open. Standard library only.

The handlers live in hooks_common, hooks_stop, hooks_budget, hooks_pre_tool and hooks_bash;
this file is the CLI and re-exports their names, so `import hooks` still reaches them.
"""

import argparse
import shutil  # noqa: F401 - tests patch hooks.shutil
import subprocess  # noqa: F401 - tests patch hooks.subprocess
import sys
import tempfile  # noqa: F401 - tests patch hooks.tempfile
import types
from pathlib import Path  # noqa: F401 - tests patch hooks.Path

import hooks_bash
import hooks_budget
import hooks_common
import hooks_pre_tool
import hooks_stop
from hooks_bash import (  # noqa: F401
    GIT_COMPILED,
    GIT_DENY,
    GIT_REASON,
    GLOBAL_WITH_VALUE,
    SHELLS,
    WRAPPERS,
    git_args,
    git_refusal,
    inner_refusal,
    is_tracked,
    pre_bash,
    rm_refusal,
    segment_refusal,
    split_unquoted,
    strip_prefix,
    under,
)
from hooks_budget import (  # noqa: F401
    BUDGET_SCRIPTS,
    BUDGET_TIMEOUT,
    CACHE_SECONDS,
    CEILING,
    USAGE_CACHE,
    budget_refusal,
    budget_script,
    span,
    usage_reading,
)
from hooks_common import (  # noqa: F401
    ROOT,
    STATE,
    Gate,
    deny,
    opted_in,
    payload,
    state_dir,
    tool_input,
)
from hooks_pre_tool import (  # noqa: F401
    AGENT_TOOLS,
    CATCH_ALL,
    LEDGER,
    LOCK_STALE_SECONDS,
    LOCK_TRIES,
    MAX_AGENTS,
    MODELS,
    PENDING_SECONDS,
    PLUGIN_AGENTS,
    RUNNING_SECONDS,
    agent_refusal,
    cap_reason,
    defined_model,
    load_ledger,
    locked_ledger,
    model_allowed,
    pre_tool_use,
    running_agents,
    subagent_start,
    subagent_stop,
)
from hooks_stop import (  # noqa: F401
    DID_NOT_RUN,
    GATES,
    HINT_LINES,
    PROGRESS,
    SKIP,
    SKIP_TAIL,
    TAIL_LINES,
    WATCHED_SUFFIXES,
    failure,
    in_scope,
    post_tool_use,
    relative,
    run,
    skip_reason,
    stop,
)

PARTS = (hooks_common, hooks_budget, hooks_pre_tool, hooks_stop, hooks_bash)


class _Facade(types.ModuleType):
    """Setting a name here sets it in every part that holds it, so a patched ROOT, LEDGER or
    run reaches the code that reads it however the parts are split."""

    def __setattr__(self, name: str, value: object) -> None:
        super().__setattr__(name, value)
        for part in PARTS:
            if name in vars(part):
                setattr(part, name, value)


sys.modules[__name__].__class__ = _Facade


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hooks.py", description="Claude Code hooks; the event payload is JSON on stdin."
    )
    events = parser.add_subparsers(dest="event", required=True, metavar="EVENT")
    events.add_parser("post-tool-use", help="mark a gate dirty after an edit in its scope")
    events.add_parser("pre-tool-use", help="refuse a forbidden, excess or over-budget agent")
    events.add_parser("pre-bash", help="refuse a subagent's working-tree discard")
    events.add_parser("subagent-start", help="record a running lane")
    events.add_parser("subagent-stop", help="free a lane")
    gate = events.add_parser("stop", help="run the dirty gates; block on failure")
    gate.add_argument(
        "--task",
        action="append",
        default=[],
        help="task to run for every dirty gate instead of its own (repeatable)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as error:
        return error.code if isinstance(error.code, int) else 2

    event = payload()
    if not event:
        return 0

    handlers = {
        "post-tool-use": post_tool_use,
        "pre-tool-use": pre_tool_use,
        "pre-bash": pre_bash,
        "subagent-start": subagent_start,
        "subagent-stop": subagent_stop,
        "stop": stop,
    }
    try:
        if args.event == "stop" and args.task:
            return stop(event, tuple(args.task))
        return handlers[args.event](event)
    except Exception:
        return 0


if __name__ == "__main__":
    sys.exit(main())
