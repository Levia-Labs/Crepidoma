"""Commit with one automatic retry when a hook only reformatted files.

Usage: commit_retry.py <message>
Runs `git commit`. If it fails and the failed hooks all rewrote files ("files were
modified by this hook"), re-stages tracked changes and commits once more. Any other
failure stops. Prints failed hook lines, then the commit id.
"""

from __future__ import annotations

import re
import subprocess
import sys

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
HOOK_LINE = re.compile(
    r"^(?P<name>.+?)\.{3,}(?P<status>Passed|Failed|Skipped|\(no files to check\).*)$"
)


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")


def failed_hooks(output: str) -> list[tuple[str, list[str]]]:
    """Return (hook line, detail lines) per failed hook in pre-commit output."""
    hooks: list[tuple[str, list[str]]] = []
    for raw in ANSI.sub("", output).splitlines():
        line = raw.rstrip()
        match = HOOK_LINE.match(line)
        if match:
            if match["status"] == "Failed":
                hooks.append((line, []))
            else:
                hooks.append(("", []))
        elif hooks and line.strip():
            hooks[-1][1].append(line.strip())
    return [h for h in hooks if h[0]]


def only_formatted(hooks: list[tuple[str, list[str]]]) -> bool:
    # Formatters (gofmt, prettier, ruff format, whitespace fixers) all announce this
    # exact line; a real lint error never does.
    return bool(hooks) and all(
        any("files were modified by this hook" in d for d in detail) for _, detail in hooks
    )


def report(hooks: list[tuple[str, list[str]]], output: str) -> None:
    if hooks:
        for line, _ in hooks:
            print(line)
    else:
        print(ANSI.sub("", output).strip())


def commit(message: str) -> int:
    first = run(["git", "commit", "-m", message])
    if first.returncode != 0:
        output = first.stdout + first.stderr
        hooks = failed_hooks(output)
        if not only_formatted(hooks):
            report(hooks, output)
            return first.returncode
        # Hooks rewrote files in the work tree; stage the rewrites and try once more.
        run(["git", "add", "-u"])
        second = run(["git", "commit", "-m", message])
        if second.returncode != 0:
            output = second.stdout + second.stderr
            report(failed_hooks(output), output)
            return second.returncode
    head = run(["git", "rev-parse", "--short", "HEAD"]).stdout.strip()
    print(f"commit {head}")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: commit_retry.py <message>", file=sys.stderr)
        return 2
    return commit(argv[0])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
