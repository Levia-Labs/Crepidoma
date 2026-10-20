#!/usr/bin/env python3
"""Subagent pool: list finished agents of the current session and steer dispatch to reuse them.

Usage: agent_pool.py list [--type T] [--max-context N] [--ttl S] [--session ID] [--top N] [--json]
       agent_pool.py hook   (PreToolUse hook on Agent|Task; reads the event from stdin)

`list` prints one line per finished agent: id, type, idle seconds, last-turn context tokens and a
verdict: `reuse` (idle < ttl and context < max) or `rotate`. `hook` denies a fresh main-thread
Agent call when a `reuse` agent of the same subagent_type exists; `[fresh]` in the description,
no candidate or any error allows it. Env: CREPIDOMA_POOL_TTL, CREPIDOMA_POOL_MAX_CONTEXT.
"""

import argparse
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

TTL = 300
MAX_CONTEXT = 40000
TAIL_BYTES = 262144


def context_tokens(usage: dict) -> int:
    keys = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
    return sum(int(usage.get(key) or 0) for key in keys)


def verdict(idle: float, context: int, ttl: float, max_context: int) -> str:
    return "reuse" if idle < ttl and context < max_context else "rotate"


def project_slug(cwd: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "-", cwd)


def projects_root() -> Path:
    base = os.environ.get("CLAUDE_CONFIG_DIR") or str(Path.home() / ".claude")
    return Path(base) / "projects"


def find_session(root: Path, slug: str, session: str | None) -> Path | None:
    proj = root / slug
    if session:
        found = proj / session
        return found if found.is_dir() else None
    dirs = [p for p in proj.iterdir() if p.is_dir()] if proj.is_dir() else []
    return max(dirs, key=lambda p: p.stat().st_mtime, default=None)


def parse_time(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(UTC)


def read_agent(path: Path, now: datetime) -> dict | None:
    """Return id, type, idle and context of a finished agent, or None."""
    try:
        meta = json.loads(path.with_suffix(".meta.json").read_text(encoding="utf-8"))
        if not meta.get("finished"):
            return None
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            handle.seek(max(0, handle.tell() - TAIL_BYTES))
            lines = handle.read().decode("utf-8", errors="replace").splitlines()
    except (OSError, ValueError):
        return None
    when = usage = None
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if not isinstance(entry, dict):
            continue
        if when is None and isinstance(entry.get("timestamp"), str):
            when = entry["timestamp"]
        message = entry.get("message")
        if usage is None and isinstance(message, dict) and isinstance(message.get("usage"), dict):
            usage = message["usage"]
        if when and usage:
            break
    if not when or usage is None:
        return None
    try:
        idle = max(0.0, (now - parse_time(when)).total_seconds())
    except ValueError:
        return None
    return {
        "id": path.stem.removeprefix("agent-"),
        "type": str(meta.get("agentType") or ""),
        "idle": idle,
        "context": context_tokens(usage),
    }


def pool(
    sub: Path, now: datetime, ttl: float, max_context: int, kind: str | None = None
) -> list[dict]:
    rows = []
    for path in sorted(sub.glob("agent-*.jsonl")):
        row = read_agent(path, now)
        if row and (not kind or row["type"] == kind):
            row["verdict"] = verdict(row["idle"], row["context"], ttl, max_context)
            rows.append(row)
    return sorted(rows, key=lambda r: r["idle"])


def decide(event: dict, sub: Path, now: datetime, ttl: float, max_context: int) -> dict | None:
    """Deny output for a main-thread Agent call that should reuse a pooled agent, else None."""
    if event.get("tool_name") not in ("Agent", "Task") or event.get("agent_id"):
        return None
    given = event.get("tool_input")
    if not isinstance(given, dict) or "[fresh]" in str(given.get("description") or ""):
        return None
    kind = str(given.get("subagent_type") or "")
    if not kind:
        return None
    for row in pool(sub, now, ttl, max_context, kind):
        if row["verdict"] == "reuse":
            reason = (
                f"reuse {row['id']} via SendMessage (context {row['context']} tok, "
                f"idle {round(row['idle'])} s); "
                "start fresh only by putting [fresh] in the description"
            )
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
    return None


def env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name) or default)
    except ValueError:
        return default


def session_subagents(session: str | None, cwd: str) -> Path | None:
    found = find_session(projects_root(), project_slug(cwd), session)
    return found / "subagents" if found else None


def run_hook() -> int:
    try:
        event = json.loads(sys.stdin.read())
        sub = session_subagents(event.get("session_id"), str(event.get("cwd") or Path.cwd()))
        if sub is None:
            return 0
        ttl, cap = (
            env_int("CREPIDOMA_POOL_TTL", TTL),
            env_int("CREPIDOMA_POOL_MAX_CONTEXT", MAX_CONTEXT),
        )
        result = decide(event, sub, datetime.now(UTC), ttl, cap)
        if result:
            print(json.dumps(result))
    except Exception:  # fail open: a pool error must never block dispatch
        return 0
    return 0


def run_list(args: argparse.Namespace) -> int:
    sub = session_subagents(args.session, str(Path.cwd()))
    if sub is None:
        print("no session", file=sys.stderr)
        return 1
    rows = pool(sub, datetime.now(UTC), args.ttl, args.max_context, args.type)[: args.top]
    if args.json:
        print(json.dumps(rows))
    for row in [] if args.json else rows:
        print(f"{row['id']} {row['type']} {round(row['idle'])} {row['context']} {row['verdict']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    lst = commands.add_parser("list")
    lst.add_argument("--type")
    lst.add_argument("--max-context", type=int, default=MAX_CONTEXT)
    lst.add_argument("--ttl", type=int, default=TTL)
    lst.add_argument("--session")
    lst.add_argument("--top", type=int, default=20)
    lst.add_argument("--json", action="store_true")
    commands.add_parser("hook")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    return run_hook() if args.command == "hook" else run_list(args)


if __name__ == "__main__":
    sys.exit(main())
