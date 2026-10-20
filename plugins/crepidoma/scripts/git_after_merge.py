"""Reset a repo to its default branch after a PR merge and print one receipt line.

Usage: git_after_merge.py <repo-path> [branch]

Switches to the default branch, fast-forward pulls (with prune), updates submodules, deletes
local branches already merged or whose upstream is gone (or only the named branch), then prints
`<branch> <sha> <subject> | dirty N | deleted a,b`. Exit 0 ok, 1 a step failed, 2 bad path.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


def default_branch(symbolic_ref: str) -> str:
    ref = symbolic_ref.strip()
    prefix = "refs/remotes/origin/"
    return ref[len(prefix) :] if ref.startswith(prefix) and len(ref) > len(prefix) else "main"


def branches_to_delete(merged: str, verbose: str, default: str, current: str) -> list[str]:
    names: list[str] = []
    for line in merged.splitlines():
        if line[:1] in ("*", "+"):
            continue
        names.append(line.strip())
    for line in verbose.splitlines():
        if line[:1] in ("*", "+"):
            continue
        m = re.match(r"\s+(\S+)\s+\S+\s+\[[^\]]*: gone\]", line)
        if m:
            names.append(m.group(1))
    out: list[str] = []
    for n in names:
        if n and n not in (default, current) and n not in out:
            out.append(n)
    return out


def dirty_count(status: str) -> int:
    return len([ln for ln in status.splitlines() if ln.strip()])


def git(path: str, args: list[str]) -> tuple[int, str]:
    p = subprocess.run(
        ["git", "-C", path, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return p.returncode, p.stdout if p.returncode == 0 else p.stdout + p.stderr


def step(path: str, name: str, args: list[str]) -> str:
    rc, out = git(path, args)
    if rc != 0:
        first = next((ln for ln in out.splitlines() if ln.strip()), "")
        raise RuntimeError(f"after-merge: {name} failed: {first[:160]}")
    return out


def run(path: str, named: str | None) -> str:
    _, ref = git(path, ["symbolic-ref", "refs/remotes/origin/HEAD"])
    default = default_branch(ref)
    step(path, "switch", ["switch", default])
    step(path, "pull", ["pull", "--ff-only", "--prune"])
    step(path, "submodule", ["submodule", "update", "--init", "--recursive"])
    if named:
        doomed = [] if named == default else [named]
    else:
        merged = step(path, "branch", ["branch", "--merged", default])
        verbose = step(path, "branch", ["branch", "-vv"])
        current = step(path, "branch", ["branch", "--show-current"]).strip()
        doomed = branches_to_delete(merged, verbose, default, current)
    for name in doomed:
        step(path, "branch -D", ["branch", "-D", name])
    head = step(path, "log", ["log", "-1", "--format=%h %s"]).strip()
    dirty = dirty_count(step(path, "status", ["status", "--short"]))
    return f"{default} {head} | dirty {dirty} | deleted {','.join(doomed) or 'none'}"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="git_after_merge")
    p.add_argument("path")
    p.add_argument("branch", nargs="?", default=None)
    a = p.parse_args(argv)
    if not Path(a.path).is_dir():
        print(f"after-merge: not a directory: {a.path}")
        return 2
    try:
        print(run(a.path, a.branch))
    except RuntimeError as e:
        print(e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
