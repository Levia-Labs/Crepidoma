"""Print the total duplicated-lines percent from a jscpd JSON report.

Usage: jscpd_pct.py <report-dir-or-file>. Exit 1 when the report is missing or malformed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPORT_NAME = "jscpd-report.json"


def parse_percentage(text: str) -> float:
    """Return statistics.total.percentage from report JSON text."""
    data = json.loads(text)
    return float(data["statistics"]["total"]["percentage"])


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: jscpd_pct.py <report-dir-or-file>", file=sys.stderr)
        return 2
    path = Path(argv[0])
    if path.is_dir():
        path = path / REPORT_NAME
    try:
        pct = parse_percentage(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"jscpd report unreadable: {exc}", file=sys.stderr)
        return 1
    print(f"{pct:g}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
