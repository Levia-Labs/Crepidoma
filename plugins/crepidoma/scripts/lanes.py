#!/usr/bin/env python3
"""List and reset subagent lanes, and write a save-state note for a later session.

Usage: lanes.py list | reset [--stale] | handoff [--out .claude/handoff.md]

The ledger format, location and limits belong to hooks.py and are imported, not copied. The
ledger holds no agent type, so `list` shows `-` in that column.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import hooks
import hooks_common
import hooks_pre_tool
import hooks_stop

HANDOFF = ".claude/handoff.md"
RECENT_COMMITS = 5


def git(*args: str) -> str:
    return hooks_stop.run("git", *args).stdout


def raw_count() -> int:
    """Entries on disk, expired ones included (load_ledger drops those)."""
    try:
        state = json.loads(hooks_pre_tool.LEDGER.read_text(encoding="utf-8"))
        return len(state["running"]) + len(state["pending"])
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return 0


def list_lanes() -> int:
    now = time.time()
    state = hooks.load_ledger(now)
    for kind in ("running", "pending"):
        for lane, since in state[kind].items():
            print(f"{lane} - {hooks.span(now - since)} {kind}")
    running, pending = len(state["running"]), len(state["pending"])
    print(f"{running} running, {pending} pending, cap {hooks.MAX_AGENTS}")
    return 0


def reset(stale: bool) -> int:
    before = raw_count()
    with hooks.locked_ledger() as state:
        # The ledger loads pruned: entries past their age limit are already gone.
        if not stale:
            state["running"].clear()
            state["pending"].clear()
        after = len(state["running"]) + len(state["pending"])
    print(f"removed {before - after}")
    return 0


def todo_count() -> int:
    try:
        text = (hooks_common.ROOT / "TODO.md").read_text(encoding="utf-8")
    except OSError:
        return 0
    return sum(line.count("TODO") for line in text.splitlines())


def handoff(out: str) -> int:
    branch = git("rev-parse", "--abbrev-ref", "HEAD").strip() or "unknown"
    commits = git("log", "--oneline", f"-{RECENT_COMMITS}").strip().splitlines()
    status = [line for line in git("status", "--short").splitlines() if line.strip()]
    untracked = sum(line.startswith("??") for line in status)
    state = hooks.load_ledger(time.time())
    lines = [
        "# Handoff",
        "",
        f"branch: {branch}",
        f"status: {len(status) - untracked} changed, {untracked} untracked",
        f"running lanes: {len(state['running'])}",
        f"open TODO markers: {todo_count()}",
        "",
        f"last {RECENT_COMMITS} commits:",
        *(f"- {commit}" for commit in commits),
    ]
    path = Path(out)
    if not path.is_absolute():
        path = hooks_common.ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")
    print(f"{path} {len(lines)} lines")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lanes.py", description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="running and pending lanes, then counts and the cap")
    drop = commands.add_parser("reset", help="clear lanes and print how many were removed")
    drop.add_argument("--stale", action="store_true", help="only lanes past their age limit")
    note = commands.add_parser("handoff", help="write a save-state note for a later session")
    note.add_argument("--out", default=HANDOFF, help="note path (default %(default)s)")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as error:
        return error.code if isinstance(error.code, int) else 2
    if args.command == "list":
        return list_lanes()
    if args.command == "reset":
        return reset(args.stale)
    return handoff(args.out)


if __name__ == "__main__":
    sys.exit(main())
