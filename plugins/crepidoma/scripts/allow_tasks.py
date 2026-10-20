#!/usr/bin/env python3
"""Keep .claude/settings.json permissions consistent with the Taskfile interface.

Findings: an allow rule for a Bash command that bypasses a task doing the same job, an allow rule
naming a task that no longer exists, any PowerShell allow (PowerShell must be denied).

Usage: allow_tasks.py check [--settings .claude/settings.json] | report [--settings PATH]
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_SETTINGS = Path(".claude") / "settings.json"
BASH_RULE = re.compile(r"^Bash\((.*)\)$")
TASK_RULE = re.compile(r"^task\s+([A-Za-z0-9_.:-]+?)(?::\*)?(?:\s+\*)?$")
# Tool command -> task name segments that cover the same job.
TOOL_SEGMENTS = {
    "ruff": ("lint", "format", "fmt"),
    "black": ("format", "fmt"),
    "flake8": ("lint",),
    "pylint": ("lint",),
    "eslint": ("lint",),
    "prettier": ("format", "fmt"),
    "pytest": ("test", "tests"),
    "mypy": ("type", "types", "typecheck"),
    "pyright": ("type", "types", "typecheck"),
    "tsc": ("type", "types", "typecheck"),
    "jest": ("test", "tests"),
    "vitest": ("test", "tests"),
}


def run(cmd: list[str]) -> str:
    """Return stdout of `cmd`; raise on failure."""
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", check=True)
    return result.stdout


def task_names() -> set[str]:
    data = json.loads(run(["task", "--list-all", "--json"]))
    return {t["name"] for t in data.get("tasks", [])}


def load_permissions(path: Path) -> dict:
    settings = json.loads(path.read_text(encoding="utf-8"))
    return settings.get("permissions", {})


def bypassed_task(command: str, names: set[str]) -> str | None:
    """Name of an existing task covering the same job as `command`, else None."""
    words = command.split()
    if not words or words[0] == "task":
        return None
    wanted = {words[0], *TOOL_SEGMENTS.get(words[0], ())}
    for name in sorted(names):
        if wanted & set(name.split(":")):
            return name
    return None


def task_exists(name: str, names: set[str], wildcard: bool) -> bool:
    if name in names:
        return True
    return wildcard and any(n.startswith(name + ":") for n in names)


def findings(allow: list[str], names: set[str]) -> list[str]:
    found = []
    for rule in allow:
        if rule.startswith("PowerShell"):
            found.append(f"{rule}: PowerShell must be denied, not allowed")
            continue
        match = BASH_RULE.match(rule)
        if not match:
            continue
        command = match.group(1).strip()
        task = TASK_RULE.match(command)
        if task:
            wildcard = command.endswith("*")
            if task.group(1) != "*" and not task_exists(task.group(1), names, wildcard):
                found.append(f"{rule}: task {task.group(1)} does not exist")
            continue
        covering = bypassed_task(command, names)
        if covering:
            found.append(f"{rule}: bypasses task {covering}")
    return found


def counts(rules: list[str]) -> dict[str, int]:
    tally: dict[str, int] = {}
    for rule in rules:
        tool = rule.split("(", 1)[0]
        tally[tool] = tally.get(tool, 0) + 1
    return tally


def cmd_check(path: Path) -> int:
    permissions = load_permissions(path)
    found = findings(permissions.get("allow", []), task_names())
    for line in found:
        print(line)
    return 1 if found else 0


def cmd_report(path: Path) -> int:
    permissions = load_permissions(path)
    for kind in ("allow", "deny"):
        for tool, n in sorted(counts(permissions.get(kind, [])).items()):
            print(f"{kind} {tool}: {n}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("check", "report"):
        p = sub.add_parser(name)
        p.add_argument("--settings", type=Path, default=DEFAULT_SETTINGS)
    args = parser.parse_args(argv)
    try:
        if args.command == "check":
            return cmd_check(args.settings)
        return cmd_report(args.settings)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
