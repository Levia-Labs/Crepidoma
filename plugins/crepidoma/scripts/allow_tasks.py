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
INTERPRETERS = {"python", "python3", "node", "xargs", "find"}
SHELLS = {"sh", "bash"}
WRAPPERS = {
    "uv",
    "uvx",
    "npx",
    "env",
    "python",
    "python3",
    "node",
    "pipx",
    "poetry",
    "sudo",
    "time",
}
# Launcher options whose value is a separate word, not the program.
VALUE_OPTIONS = {"--python", "--with", "--from"}
# Shell builtins and generic utilities: sharing one with a task is not a bypass.
GENERIC = {
    "echo", "printf", "test", "[", "[[", "grep", "wc", "tr", "cat", "sed", "awk", "head", "tail",
    "sort", "ls", "cd", "command", "exit", "true", "false", "diff", "file", "cp", "mv", "rm",
    "mkdir", "touch", "if", "then", "else", "fi", "for", "do", "done", "set", "export", "cut",
}  # fmt: skip
SEPARATORS = re.compile(r"&&|\|\||[|;]")


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


def task_executables(names: set[str]) -> dict[str, set[str]]:
    """Map each task to the executables its commands run, from `task --summary`."""
    try:
        text = run(["task", "--summary", *sorted(names)])
    except subprocess.CalledProcessError:
        return {}
    tools: dict[str, set[str]] = {}
    current = None
    in_commands = False
    for line in text.splitlines():
        head = re.match(r"^task: (\S+)$", line)
        if head:
            current, in_commands = head.group(1), False
            tools.setdefault(current, set())
        elif line.startswith("commands:"):
            in_commands = True
        elif in_commands and current and line.startswith(" - "):
            tools[current].update(executables(line[3:]))
    return tools


def executables(command: str) -> set[str]:
    """Programs a shell command line runs, looking through launchers such as `uv run`."""
    found = set()
    for part in SEPARATORS.split(command):
        words = part.replace('"', " ").replace("'", " ").split()
        while words and (words[0] in WRAPPERS or words[0].startswith("-") or words[0] == "run"):
            if words[0] in WRAPPERS:
                found.add(words[0].rsplit("/", 1)[-1])
            words.pop(0)
            while words and words[0].startswith("-"):
                if words.pop(0) in VALUE_OPTIONS and words:
                    words.pop(0)
        if words:
            found.add(words[0].rsplit("/", 1)[-1])
    return found


def is_interpreter(command: str) -> bool:
    words = command.split()
    if not words:
        return False
    return words[0] in INTERPRETERS or (words[0] in SHELLS and len(words) > 1 and words[1] == "-c")


def bypassed_task(command: str, tools: dict[str, set[str]]) -> str | None:
    """Name of a task whose commands run the same tool as `command`, else None."""
    words = command.split()
    if not words or words[0] == "task" or words[0] in INTERPRETERS | SHELLS:
        return None
    for name in sorted(tools):
        if words[0] not in GENERIC and words[0] in tools[name]:
            return name
    return None


def task_matches(pattern: str, name: str) -> bool:
    """go-task wildcard: `*` matches one name segment or more."""
    regex = ".+".join(re.escape(part) for part in pattern.split("*"))
    return re.fullmatch(regex, name) is not None


def task_exists(name: str, names: set[str], wildcard: bool) -> bool:
    if name in names:
        return True
    if any("*" in n and task_matches(n, name) for n in names):
        return True
    return wildcard and any(n.startswith(name + ":") for n in names)


def findings(allow: list[str], names: set[str]) -> list[str]:
    found = []
    tools = None
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
        if is_interpreter(command):
            found.append(f"{rule}: interpreter or wrapper")
            continue
        if tools is None:
            tools = task_executables(names)
        covering = bypassed_task(command, tools)
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
