"""Ratchet quality metrics so they never get worse.

long-files: files over --max-lines must be in the baseline and may not grow.
metric: one number compared with a baseline value; --direction says which way is better.
A missing metric baseline is created from the first value.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def count_lines(path: Path) -> int:
    with path.open("rb") as handle:
        return sum(1 for _ in handle)


def read_baseline(path: Path) -> dict[str, int]:
    if not path.is_file():
        return {}
    entries: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        name, _, value = line.rpartition("\t")
        entries[name] = int(value)
    return entries


def write_baseline(path: Path, entries: dict[str, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(f"{name}\t{lines}\n" for name, lines in sorted(entries.items()))
    path.write_text(body, encoding="utf-8", newline="\n")


def long_files(files: list[str], baseline: Path, max_lines: int, update: bool) -> int:
    current: dict[str, int] = {}
    for name in files:
        path = Path(name)
        if path.is_file():
            lines = count_lines(path)
            if lines > max_lines:
                current[path.as_posix()] = lines
    if update:
        write_baseline(baseline, current)
        print(f"baseline: {len(current)} long files")
        return 0
    allowed = read_baseline(baseline)
    failures = []
    for name, lines in sorted(current.items()):
        limit = allowed.get(name)
        if limit is None:
            failures.append(f"{name}: {lines} lines > {max_lines} (new long file)")
        elif lines > limit:
            failures.append(f"{name}: {lines} lines > baseline {limit}")
    for failure in failures:
        print(failure)
    return 1 if failures else 0


def metric(baseline: Path, value: float, direction: str, update: bool) -> int:
    text = baseline.read_text(encoding="utf-8").strip() if baseline.is_file() else ""
    if not text:
        baseline.parent.mkdir(parents=True, exist_ok=True)
        baseline.write_text(f"{value}\n", encoding="utf-8", newline="\n")
        print(f"baseline set: {value}")
        return 0
    base = float(text)
    worse = value < base if direction == "up" else value > base
    if worse:
        print(f"{value} is worse than baseline {base} ({direction} is better)")
        return 1
    if update and value != base:
        baseline.write_text(f"{value}\n", encoding="utf-8", newline="\n")
        print(f"baseline improved: {base} -> {value}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    files_parser = sub.add_parser("long-files")
    files_parser.add_argument("--baseline", type=Path, default=Path(".ratchet/long-files.baseline"))
    files_parser.add_argument("--max-lines", type=int, default=400)
    files_parser.add_argument("--update", action="store_true")
    files_parser.add_argument("--git", action="store_true", help="check every tracked file")
    files_parser.add_argument("files", nargs="*")
    metric_parser = sub.add_parser("metric")
    metric_parser.add_argument("--baseline", type=Path, required=True)
    metric_parser.add_argument("--value", type=float, required=True)
    metric_parser.add_argument("--direction", choices=["up", "down"], required=True)
    metric_parser.add_argument("--update", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "metric":
        return metric(args.baseline, args.value, args.direction, args.update)
    files = args.files
    if args.git:
        listing = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True)
        files = listing.stdout.splitlines()
    return long_files(files, args.baseline, args.max_lines, args.update)


if __name__ == "__main__":
    raise SystemExit(main())
