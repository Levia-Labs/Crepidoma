"""Print a numbered line range of a file, at most 60 lines.

Usage: read_range.py FILE START END (1-based, inclusive). Larger ranges are refused with a hint.
"""

from __future__ import annotations

import sys
from pathlib import Path

MAX_LINES = 60


def main(argv: list[str]) -> int:
    if len(argv) != 3 or not all(part.isdigit() for part in argv[1:]):
        print("usage: read_range.py FILE START END", file=sys.stderr)
        return 2
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
    # A Windows console's legacy code page cannot encode every character a UTF-8 file holds.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    for number in range(start, min(end, len(lines)) + 1):
        print(f"{number}\t{lines[number - 1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
