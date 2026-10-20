"""Compare a pillar checkout with Crepidoma-owned files.

Usage: drift_check.py PILLAR [--map FILE] [--root DIR] [--report FILE]
States: duplicate (identical copy, delete it), drifted (local divergence), absent (linked, good).
Exit 0 when every entry is absent, 1 on duplicate or drifted, 2 when PILLAR is not a directory.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import tomllib
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MAP = ROOT / "tools" / "drift_map.toml"
MAX_SHOWN = 15
STATES = ("duplicate", "drifted", "absent")


def load_map(path: Path) -> list[dict]:
    return tomllib.loads(path.read_text(encoding="utf-8"))["file"]


def fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def check(pillar: Path, entries: list[dict], root: Path) -> list[tuple[str, str, str]]:
    rows = []
    for entry in entries:
        source = root / entry["crepidoma"]
        copy = next((pillar / c for c in entry["pillar"] if (pillar / c).is_file()), None)
        if copy is None:
            rows.append(("absent", entry["crepidoma"], "-"))
            continue
        state = "duplicate" if fingerprint(copy) == fingerprint(source) else "drifted"
        rows.append((state, entry["crepidoma"], copy.relative_to(pillar).as_posix()))
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pillar", type=Path)
    parser.add_argument("--map", type=Path, default=DEFAULT_MAP)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    if not args.pillar.is_dir():
        print(f"not a directory: {args.pillar}", file=sys.stderr)
        return 2
    rows = check(args.pillar, load_map(args.map), args.root)
    lines = [f"{state}\t{source}\t{copy}" for state, source, copy in rows]
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    flagged = [line for line in lines if not line.startswith("absent")]
    for line in flagged[:MAX_SHOWN]:
        print(line)
    if len(flagged) > MAX_SHOWN:
        print(f"... {len(flagged) - MAX_SHOWN} more")
    counts = Counter(row[0] for row in rows)
    print(" ".join(f"{state}={counts[state]}" for state in STATES))
    return 1 if flagged else 0


if __name__ == "__main__":
    raise SystemExit(main())
