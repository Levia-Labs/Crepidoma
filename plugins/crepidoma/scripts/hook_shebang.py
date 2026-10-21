"""Rewrite `#!/bin/sh` to `#!/usr/bin/env sh` in .git/hooks/*.legacy.

`pre-commit install` moves a Git LFS hook to `<hook>.legacy`; pre-commit on Windows
cannot resolve /bin/sh, so every push fails. Idempotent. Usage: hook_shebang.py [--root DIR]
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

OLD = b"#!/bin/sh"
NEW = b"#!/usr/bin/env sh"


def hooks_dir(root: Path) -> Path:
    done = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--git-path", "hooks"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    path = Path(done.stdout.strip())
    return path if path.is_absolute() else root / path


def rewrite(hooks: Path) -> int:
    count = 0
    for hook in sorted(hooks.glob("*.legacy")):
        data = hook.read_bytes()
        first, sep, rest = data.partition(b"\n")
        if first.rstrip(b"\r") != OLD:
            continue
        hook.write_bytes(NEW + first[len(OLD) :] + sep + rest)
        count += 1
    return count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    print(f"hook shebangs: {rewrite(hooks_dir(args.root))} rewritten")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
