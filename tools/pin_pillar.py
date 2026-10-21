"""Pin a pillar's Crepidoma submodule to a release tag without discarding changes.

Usage: pin_pillar.py PILLAR TAG [--submodule .crepidoma]

Refuses (exit 1, one stderr line) on a dirty submodule, staged changes outside the
submodule, or a tag that is not vX.Y.Z or does not exist after `fetch --tags`.
Prints one receipt line. Exit 0 ok, 1 refused or failed, 2 usage.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

TAG = re.compile(r"^v\d+\.\d+\.\d+$")


class Refusal(Exception):
    pass


def valid_tag(tag: str) -> bool:
    return TAG.fullmatch(tag) is not None


def staged_outside(staged: list[str], submodule: str) -> list[str]:
    return [p for p in staged if p != submodule]


def receipt(name: str, submodule: str, old: str, tag: str, new: str) -> str:
    if old == new:
        return f"{name} already at {tag}"
    return f"{name} {submodule} {old[:7]} -> {tag} {new[:7]}"


def git(root: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, encoding="utf-8"
    )
    if done.returncode:
        lines = (done.stderr or done.stdout).strip().splitlines()
        raise Refusal(f"git {args[0]} failed: {lines[-1] if lines else done.returncode}")
    return done.stdout.strip()


def pin(pillar: Path, tag: str, submodule: str) -> str:
    if not valid_tag(tag):
        raise Refusal(f"refusing: tag {tag!r} does not match vX.Y.Z")
    sub = pillar / submodule
    if not sub.is_dir():
        raise Refusal(f"refusing: submodule {sub} not found")
    if git(sub, "status", "--porcelain"):
        raise Refusal(f"refusing: submodule {submodule} has uncommitted changes")
    staged = staged_outside(git(pillar, "diff", "--cached", "--name-only").splitlines(), submodule)
    if staged:
        raise Refusal(f"refusing: pillar has staged changes outside {submodule}: {staged[0]}")
    git(sub, "fetch", "--tags", "origin")
    try:
        target = git(sub, "rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}")
    except Refusal:
        raise Refusal(f"refusing: tag {tag} not found in {submodule}") from None
    old = git(sub, "rev-parse", "HEAD")
    if old != target:
        git(sub, "checkout", "--detach", tag)
    git(pillar, "add", submodule)
    return receipt(pillar.resolve().name, submodule, old, tag, target)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pillar", type=Path)
    parser.add_argument("tag")
    parser.add_argument("--submodule", default=".crepidoma")
    args = parser.parse_args(argv)
    try:
        print(pin(args.pillar, args.tag, args.submodule))
    except Refusal as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
