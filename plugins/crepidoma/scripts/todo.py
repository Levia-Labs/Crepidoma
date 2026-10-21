#!/usr/bin/env python3
"""List, show, add, update and drop entries of a repo-root TODO.md.

Usage: todo.py list [--status S] [--class C] [--limit N] | show ID |
       add --title T --class C [--body B] | set ID --status S | drop ID

Each entry is a `## <id> <title>` heading, then `status:` and `class:` lines, then a free body.
Written files match prettier output (blank line after each heading). Text before the first
entry is kept as is. `--file PATH` overrides the default `TODO.md` in
`CLAUDE_PROJECT_DIR` or the current directory. Exit codes: 0 ok, 1 unknown id or missing file,
2 usage error.
"""

import argparse
import os
import re
import sys
from pathlib import Path

HEADING = re.compile(r"^## (\d+) (.+)$")
DEFAULT_LIMIT = 20


def default_file() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd()) / "TODO.md"


def parse(text: str) -> tuple[list[str], list[list[str]]]:
    """Split into preamble lines and one line-list per entry."""
    preamble: list[str] = []
    entries: list[list[str]] = []
    for line in text.splitlines():
        if HEADING.match(line):
            entries.append([line])
        elif entries:
            if len(entries[-1]) == 1 and not line.strip():
                continue
            entries[-1].append(line)
        else:
            preamble.append(line)
    return preamble, entries


def render(preamble: list[str], entries: list[list[str]]) -> str:
    lines = list(preamble)
    for entry in entries:
        while entry and not entry[-1].strip():
            entry.pop()
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend([entry[0], "", *entry[1:]])
    return "\n".join(lines) + "\n"


def ident(entry: list[str]) -> int:
    return int(HEADING.match(entry[0]).group(1))


def title(entry: list[str]) -> str:
    return HEADING.match(entry[0]).group(2)


def field(entry: list[str], key: str) -> str:
    prefix = f"{key}:"
    for line in entry[1:]:
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
        if not line.strip():
            break
    return ""


def set_field(entry: list[str], key: str, value: str) -> None:
    prefix = f"{key}:"
    for index, line in enumerate(entry[1:], 1):
        if line.startswith(prefix):
            entry[index] = f"{prefix} {value}"
            return
        if not line.strip():
            break
    entry.insert(1, f"{prefix} {value}")


def find(entries: list[list[str]], number: int) -> list[str] | None:
    return next((entry for entry in entries if ident(entry) == number), None)


def load(path: Path) -> tuple[list[str], list[list[str]]]:
    return parse(path.read_text(encoding="utf-8"))


def save(path: Path, preamble: list[str], entries: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(render(preamble, entries))


def missing(number: int) -> int:
    print(f"no entry {number}")
    return 1


def list_entries(path: Path, status: str | None, kind: str | None, limit: int) -> int:
    _, entries = load(path)
    rows = [
        f"{ident(entry)} {field(entry, 'status')} {field(entry, 'class')} {title(entry)}"
        for entry in entries
        if (status is None or field(entry, "status") == status)
        and (kind is None or field(entry, "class") == kind)
    ]
    shown = rows if limit <= 0 else rows[:limit]
    if shown:
        print("\n".join(shown))
    if len(shown) < len(rows):
        print(f"... {len(rows) - len(shown)} more")
    return 0


def show(path: Path, number: int) -> int:
    _, entries = load(path)
    entry = find(entries, number)
    if entry is None:
        return missing(number)
    print("\n".join(entry).rstrip())
    return 0


def add(path: Path, heading: str, kind: str, body: str) -> int:
    if not heading.strip() or "\n" in heading:
        print("title must be one non-empty line")
        return 2
    if not kind.strip() or any(char.isspace() for char in kind):
        print("class must be one word")
        return 2
    body_lines = body.splitlines()
    if any(HEADING.match(line) for line in body_lines):
        print("body must not contain an entry heading")
        return 2
    preamble, entries = load(path) if path.exists() else (["# TODO"], [])
    number = max((ident(entry) for entry in entries), default=0) + 1
    entry = [f"## {number} {heading.strip()}", "status: open", f"class: {kind.strip()}"]
    if body_lines:
        entry += ["", *body_lines]
    entries.append(entry)
    save(path, preamble, entries)
    print(number)
    return 0


def set_status(path: Path, number: int, status: str) -> int:
    if not status.strip() or any(char.isspace() for char in status):
        print("status must be one word")
        return 2
    preamble, entries = load(path)
    entry = find(entries, number)
    if entry is None:
        return missing(number)
    set_field(entry, "status", status)
    save(path, preamble, entries)
    print(f"{number} status {status}")
    return 0


def drop(path: Path, number: int) -> int:
    preamble, entries = load(path)
    entry = find(entries, number)
    if entry is None:
        return missing(number)
    entries.remove(entry)
    save(path, preamble, entries)
    print(f"dropped {number}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="todo.py", description=__doc__.splitlines()[0])
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--file", type=Path, default=None, help="TODO file (default TODO.md)")
    commands = parser.add_subparsers(dest="command", required=True)
    listing = commands.add_parser("list", parents=[common], help="one line per entry")
    listing.add_argument("--status")
    listing.add_argument("--class", dest="kind")
    listing.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="0 for all")
    commands.add_parser("show", parents=[common], help="print one entry").add_argument(
        "id", type=int
    )
    new = commands.add_parser("add", parents=[common], help="append an open entry")
    new.add_argument("--title", required=True)
    new.add_argument("--class", dest="kind", required=True)
    new.add_argument("--body", default="")
    change = commands.add_parser("set", parents=[common], help="change an entry's status")
    change.add_argument("id", type=int)
    change.add_argument("--status", required=True)
    commands.add_parser("drop", parents=[common], help="remove an entry").add_argument(
        "id", type=int
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as error:
        return error.code if isinstance(error.code, int) else 2
    path = args.file or default_file()
    if args.command != "add" and not path.exists():
        print(f"no file {path}")
        return 1
    if args.command == "list":
        return list_entries(path, args.status, args.kind, args.limit)
    if args.command == "show":
        return show(path, args.id)
    if args.command == "add":
        return add(path, args.title, args.kind, args.body)
    if args.command == "set":
        return set_status(path, args.id, args.status)
    return drop(path, args.id)


if __name__ == "__main__":
    sys.exit(main())
