"""Stage exactly the given paths and print the staged list.

Usage: stage_paths.py <path>...
Refuses no paths, `.`, and paths outside the repository, so parallel agents in a shared
checkout never sweep each other's files into one commit.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, encoding="utf-8", errors="replace"
    )


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: stage_paths.py <path>... (no paths given)", file=sys.stderr)
        return 2
    top = git(["rev-parse", "--show-toplevel"])
    if top.returncode != 0:
        print("not inside a git repository", file=sys.stderr)
        return 2
    root = Path(top.stdout.strip()).resolve()
    for raw in argv:
        resolved = Path(raw).resolve()
        if raw.strip() in ("", ".", "./") or resolved == root:
            print(f"refused: {raw!r} stages the whole tree", file=sys.stderr)
            return 2
        if resolved != root and root not in resolved.parents:
            print(f"refused: {raw!r} is outside the repository", file=sys.stderr)
            return 2
    added = git(["add", "--", *argv])
    if added.returncode != 0:
        print(added.stderr.strip(), file=sys.stderr)
        return added.returncode
    print(git(["diff", "--cached", "--name-status"]).stdout.rstrip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
