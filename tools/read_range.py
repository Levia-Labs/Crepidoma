"""Print numbered line ranges of one or more files, at most 60 lines per call.

Usage:
  read_range.py FILE START END                 (legacy; no header, over 60 lines refused)
  read_range.py FILE 10-40 80-120              (several ranges; START END pairs also valid)
  read_range.py FILE_A 10-40 -- FILE_B 1-20    (several files; `--` separates groups)

Ranges are 1-based and inclusive. Overlapping or adjacent ranges in one file merge. Each block
prints `== path:start-end ==` then numbered lines. When the blocks exceed 60 lines combined,
the rest is dropped and `... truncated: N more lines requested` is printed (exit 0).
Bad syntax exits 2, an unreadable file exits 1.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

MAX_LINES = 60
SEPARATOR = "--"
_RANGE = re.compile(r"([0-9]+)-([0-9]+)")

Range = tuple[int, int]


def parse_specs(tokens: list[str]) -> list[Range]:
    """Parse `A-B` tokens and bare `A B` pairs into validated ranges; raise ValueError."""
    ranges: list[Range] = []
    pending: str | None = None
    for token in tokens:
        match = _RANGE.fullmatch(token)
        if match and pending is None:
            ranges.append((int(match[1]), int(match[2])))
        elif token.isascii() and token.isdigit():
            if pending is None:
                pending = token
            else:
                ranges.append((int(pending), int(token)))
                pending = None
        else:
            raise ValueError(f"bad range {token!r}")
    if pending is not None or not ranges:
        raise ValueError("expected at least one complete range")
    for start, end in ranges:
        if start < 1 or end < start:
            raise ValueError("range must satisfy 1 <= START <= END")
    return ranges


def merge_ranges(ranges: list[Range]) -> list[Range]:
    """Sort ranges and merge those that overlap or touch."""
    merged: list[Range] = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def parse_groups(argv: list[str]) -> list[tuple[str, list[Range]]]:
    """Split argv on `--` into (file, merged ranges) groups; raise ValueError."""
    groups: list[list[str]] = [[]]
    for token in argv:
        if token == SEPARATOR:
            groups.append([])
        else:
            groups[-1].append(token)
    if not all(groups):
        raise ValueError("empty group around `--`")
    return [(group[0], merge_ranges(parse_specs(group[1:]))) for group in groups]


def legacy(argv: list[str]) -> int | None:
    """Handle the original `FILE START END` form; None when argv is not that form."""
    if len(argv) != 3 or not all(part.isdigit() for part in argv[1:]):
        return None
    start, end = int(argv[1]), int(argv[2])
    if start < 1 or end < start:
        print("range must satisfy 1 <= START <= END", file=sys.stderr)
        return 2
    if end - start + 1 > MAX_LINES:
        print(
            f"range of {end - start + 1} lines exceeds {MAX_LINES}; "
            f"read {start}-{start + MAX_LINES - 1}, then continue, or locate with repo:outline",
            file=sys.stderr,
        )
        return 2
    try:
        lines = Path(argv[0]).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        print(f"unreadable: {exc}", file=sys.stderr)
        return 1
    for number in range(start, min(end, len(lines)) + 1):
        print(f"{number}\t{lines[number - 1]}")
    return 0


def main(argv: list[str]) -> int:
    # A Windows console's legacy code page cannot encode every character a UTF-8 file holds.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    code = legacy(argv)
    if code is not None:
        return code
    try:
        groups = parse_groups(argv)
    except ValueError as exc:
        print(
            f"usage: read_range.py FILE (START END | A-B)... [-- FILE ...]: {exc}", file=sys.stderr
        )
        return 2
    texts: dict[str, list[str]] = {}
    for path, _ in groups:
        try:
            texts[path] = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            print(f"unreadable: {exc}", file=sys.stderr)
            return 1
    budget = MAX_LINES
    dropped = 0
    for path, ranges in groups:
        lines = texts[path]
        for start, end in ranges:
            if budget <= 0:
                dropped += end - start + 1
                continue
            take_end = min(end, start + budget - 1)
            print(f"== {path}:{start}-{take_end} ==")
            for number in range(start, min(take_end, len(lines)) + 1):
                print(f"{number}\t{lines[number - 1]}")
            budget -= take_end - start + 1
            dropped += end - take_end
    if dropped:
        print(f"... truncated: {dropped} more lines requested")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
