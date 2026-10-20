"""Compare a pillar checkout with Crepidoma-owned files.

Usage: drift_check.py PILLAR [--map FILE] [--root DIR] [--report FILE]
States: duplicate (identical copy, delete it), drifted (local divergence), absent (linked, good),
mirror (identical copy a tool needs at the repo root; entries marked `mirror = true`),
extended (copy holds all shared content plus pillar additions, declared in the pillar's
`.crepidoma-drift.toml`).
Declaration: `[[extended]]` tables with `path` (pillar-relative) and optional `waive`, a list of
shared facts the pillar intentionally drops. A fact is a whitespace-normalised line; for `.yml` and
`.yaml` paths it is `key|key: scalar` or `key|- item` (key = top-level key). Shared facts missing
from the copy and not waived leave it drifted.
Exit 0 when every entry is absent, mirror or extended, 1 on duplicate or drifted, 2 when PILLAR is
not a directory.
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
STATES = ("duplicate", "drifted", "extended", "mirror", "absent")
CLEAN = ("absent", "mirror", "extended")
DECLARATION = ".crepidoma-drift.toml"


def load_map(path: Path) -> list[dict]:
    return tomllib.loads(path.read_text(encoding="utf-8"))["file"]


def fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def load_declared(pillar: Path) -> dict[str, set[str]]:
    """Map pillar-relative path to the shared facts the pillar waives."""
    path = pillar / DECLARATION
    if not path.is_file():
        return {}
    tables = tomllib.loads(path.read_text(encoding="utf-8")).get("extended", [])
    return {t["path"]: set(t.get("waive", [])) for t in tables}


def facts(path: Path) -> set[str]:
    text = path.read_bytes().decode("utf-8")
    yaml = path.suffix in (".yml", ".yaml")
    found: set[str] = set()
    parent = ""
    for raw in text.splitlines():
        line = " ".join(raw.split())
        if not line or line.startswith("#"):
            continue
        if yaml and not raw[0].isspace() and not line.startswith("-"):
            parent = line.split(":", 1)[0]
            if not line.split(":", 1)[1].strip():
                continue
        if yaml:
            line = f"{parent}|{line}"
        found.add(line)
    return found


def is_extension(copy: Path, source: Path, waived: set[str]) -> bool:
    return facts(source) - waived <= facts(copy)


def check(pillar: Path, entries: list[dict], root: Path) -> list[tuple[str, str, str]]:
    rows = []
    declared = load_declared(pillar)
    for entry in entries:
        source = root / entry["crepidoma"]
        copy = next((pillar / c for c in entry["pillar"] if (pillar / c).is_file()), None)
        if copy is None:
            rows.append(("absent", entry["crepidoma"], "-"))
            continue
        same = fingerprint(copy) == fingerprint(source)
        rel = copy.relative_to(pillar).as_posix()
        if not same and rel in declared and is_extension(copy, source, declared[rel]):
            state = "extended"
        elif entry.get("mirror"):
            state = "mirror" if same else "drifted"
        else:
            state = "duplicate" if same else "drifted"
        rows.append((state, entry["crepidoma"], rel))
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
    flagged = [line for line in lines if not line.startswith(CLEAN)]
    for line in flagged[:MAX_SHOWN]:
        print(line)
    if len(flagged) > MAX_SHOWN:
        print(f"... {len(flagged) - MAX_SHOWN} more")
    counts = Counter(row[0] for row in rows)
    print(" ".join(f"{state}={counts[state]}" for state in STATES))
    return 1 if flagged else 0


if __name__ == "__main__":
    raise SystemExit(main())
