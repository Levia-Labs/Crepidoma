"""SDD ledger helpers: append a progress line, defer Low/Minor review findings as TODO entries.

Usage:
  sdd_ledger.py progress LEDGER LINE
  sdd_ledger.py defer REVIEW_FILE [--todo-file F]

Review lines read `severity | file:line | issue | fix`; Low and Minor become class `debt` entries
through the todo tool (plugins/crepidoma/scripts/todo.py).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import path_guard

TODO = Path(__file__).resolve().parent.parent / "plugins" / "crepidoma" / "scripts" / "todo.py"
DEFERRED = {"low", "minor"}


def progress(ledger: Path, line: str) -> int:
    try:
        ledger = path_guard.checked(ledger, protect_config=False)
    except ValueError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1
    if "\n" in line or "\r" in line or not line.strip():
        print("progress takes one non-empty line", file=sys.stderr)
        return 2
    existing = ledger.read_text(encoding="utf-8") if ledger.exists() else ""
    head = "" if ledger.exists() else f"# {ledger.stem}\n\n"
    glue = "\n" if existing and not existing.endswith("\n") else ""
    with ledger.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(f"{head}{glue}{line.strip()}\n")
    print(f"{ledger}: appended")
    return 0


def findings(text: str) -> list[tuple[str, str, str]]:
    """Return (location, issue, fix) for each Low or Minor line; other lines are ignored."""
    found = []
    for raw in text.splitlines():
        parts = [part.strip() for part in raw.strip().lstrip("-*0123456789. ").split("|")]
        if len(parts) >= 4 and parts[0].lower() in DEFERRED:
            found.append((parts[1], parts[2], " | ".join(parts[3:])))
    return found


def defer(review: Path, todo_file: str | None) -> int:
    try:
        if todo_file:
            todo_file = str(path_guard.checked(Path(todo_file), protect_config=False))
        items = findings(review.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"unreadable: {exc}", file=sys.stderr)
        return 1
    ids = []
    for location, issue, fix in items:
        command = [sys.executable, str(TODO), "add", "--class", "debt"]
        command += ["--title", f"{location} {issue}"[:100], "--body", f"Fix: {fix}"]
        if todo_file:
            command += ["--file", todo_file]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
        if result.returncode != 0:
            print(f"todo add failed: {result.stdout}{result.stderr}".strip(), file=sys.stderr)
            return 1
        ids.append(result.stdout.strip())
    print(f"deferred {len(ids)}: {' '.join(ids)}" if ids else "deferred 0")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[0] == "progress":
        return progress(Path(argv[1]), argv[2])
    if argv[:1] == ["defer"] and len(argv) == 2:
        return defer(Path(argv[1]), None)
    if argv[:1] == ["defer"] and len(argv) == 4 and argv[2] == "--todo-file":
        return defer(Path(argv[1]), argv[3])
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
