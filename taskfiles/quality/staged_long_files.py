"""List staged files over the line cap, reusing the ratchet's cap and exclusions.

Usage: staged_long_files.py [--max-lines N]
Prints `path: N lines > cap` per file; exit 0 always so callers decide what to do.
"""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
from pathlib import Path

# Load the ratchet by path: tools/ is not a package and the cap must stay in one place.
_SPEC = importlib.util.spec_from_file_location(
    "ratchet", Path(__file__).resolve().parents[2] / "tools" / "ratchet.py"
)
assert _SPEC and _SPEC.loader
ratchet = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ratchet)


def staged_files() -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return out.stdout.splitlines()


def over_cap(files: list[str], max_lines: int) -> list[str]:
    found = []
    for name in files:
        path = Path(name)
        if ".ratchet" in path.parts or not path.is_file():
            continue
        if path.name in ratchet.LOCKFILES or ratchet.is_binary(path):
            continue
        lines = ratchet.count_lines(path)
        if lines > max_lines:
            found.append(f"{path.as_posix()}: {lines} lines > {max_lines}")
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-lines", type=int, default=300)
    args = parser.parse_args(argv)
    for line in over_cap(staged_files(), args.max_lines):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
