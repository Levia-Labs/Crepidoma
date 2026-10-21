#!/usr/bin/env python3
"""PreToolUse hook: route a command through `rtk` when a project filter matches it (stdlib only).

rtk's own Claude hook rewrites only commands it knows, so project filters in
`.rtk/filters.toml` (for example `task validate`) never apply on their own. This hook
rewrites a simple single command that matches a filter's `match_command` to
`rtk <command>` through `hookSpecificOutput.updatedInput`, leaving the permission decision to the
normal flow. Pipes, `&&`, `;`, redirects,
subshells and substitutions are left untouched. It does nothing when rtk is not on PATH or
the filter file is missing or unparseable, and it fails open on any error.

`wrap` is shared with hooks.py so the Stop hook's gate run goes through the same routing.
"""

import json
import os
import re
import shutil
import sys
import tomllib
from pathlib import Path

COMPOUND = re.compile(r"[|&;<>()`$\n\r{}]")
# Lines of a gate run that carry no decision: pytest progress, pre-commit Passed/Skipped
# rows and prettier (unchanged) rows, each possibly followed by ANSI colour codes.
ANSI = r"(\x1b\[[0-9;]*m)*"
NOISE = re.compile(
    rf"^([.s]+\s+\[\s*\d+%\]|.*(\.{{3,}}\s*{ANSI}(Passed|Skipped)|\(unchanged\)){ANSI}\s*)$"
)


def patterns(root: Path) -> list[re.Pattern]:
    try:
        data = tomllib.loads((root / ".rtk" / "filters.toml").read_text(encoding="utf-8"))
        found = [
            re.compile(table["match_command"])
            for table in (data.get("filters") or {}).values()
            if isinstance(table, dict) and isinstance(table.get("match_command"), str)
        ]
    except (OSError, ValueError, re.error, AttributeError):
        return []
    return found


def quiet_grep(text: str) -> bool:
    """grep with -q/--quiet/--silent (also inside combined short flags like -qE)."""
    words = text.split()
    if not words or words[0] not in ("grep", "egrep", "fgrep"):
        return False
    for word in words[1:]:
        if word in ("--quiet", "--silent"):
            return True
        if re.fullmatch(r"-[A-Za-z]*q[A-Za-z]*", word):
            return True
    return False


def routed(command: str, root: Path) -> bool:
    text = command.strip()
    if not text or COMPOUND.search(text) or re.match(r"rtk(\.exe)?(\s|$)", text):
        return False
    if quiet_grep(text) or shutil.which("rtk") is None:
        return False
    return any(pattern.search(text) for pattern in patterns(root))


def wrap(command: tuple[str, ...], root: Path) -> tuple[str, ...]:
    """Prefix `rtk` to an argument vector when a project filter matches it."""
    return ("rtk", *command) if routed(" ".join(command), root) else command


def rewrite(event: dict, root: Path) -> dict | None:
    if event.get("tool_name") != "Bash":
        return None
    given = event.get("tool_input")
    command = given.get("command") if isinstance(given, dict) else None
    if not isinstance(command, str) or not routed(command, root):
        return None
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "updatedInput": {**given, "command": f"rtk {command.strip()}"},
        }
    }


def main() -> int:
    try:
        event = json.loads(sys.stdin.read())
        root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or Path.cwd())
        result = rewrite(event, root)
        if result:
            print(json.dumps(result))
    except Exception:  # noqa: S110 - a hook fails open
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
