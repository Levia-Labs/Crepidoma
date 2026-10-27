"""Exact text replacement and insertion in one file, with a one-line receipt.

Usage:
  edit_file.py replace FILE (--old TEXT | --old-file F) (--new TEXT | --new-file F) [--count N]
  edit_file.py insert-after FILE (--anchor TEXT | --anchor-file F) (--text TEXT | --text-file F)
      [--count N]

The edit fails unless the old text or anchor occurs exactly N times (default 1). The file keeps its
newline style: CRLF when it holds any CRLF, LF otherwise.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import path_guard


def newline_style(raw: str) -> str:
    return "\r\n" if "\r\n" in raw else "\n"


def adapt(text: str, style: str) -> str:
    """Rewrite the newlines of an argument to the file's style so multi-line blocks match."""
    return text.replace("\r\n", "\n").replace("\n", style)


def apply(raw: str, old: str, new: str, count: int, after: bool) -> tuple[str, int]:
    """Return the edited text; raise ValueError unless old occurs exactly count times."""
    if not old:
        raise ValueError("old text must not be empty")
    style = newline_style(raw)
    old, new = adapt(old, style), adapt(new, style)
    found = raw.count(old)
    if found != count:
        raise ValueError(f"expected {count} occurrence(s), found {found}")
    return raw.replace(old, old + new if after else new), found


def read_raw(path: Path) -> str:
    """Read without newline translation so CRLF survives (read_text lacks newline before 3.13)."""
    with path.open(encoding="utf-8", newline="") as handle:
        return handle.read()


def pick(args: argparse.Namespace, inline: str) -> str:
    path = getattr(args, f"{inline}_file")
    if path is not None:
        return read_raw(path_guard.checked(Path(path)))
    return getattr(args, inline)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="edit_file.py", description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    for name, key, value in (("replace", "old", "new"), ("insert-after", "anchor", "text")):
        sub = commands.add_parser(name)
        sub.add_argument("file", type=Path)
        for part in (key, value):
            group = sub.add_mutually_exclusive_group(required=True)
            group.add_argument(f"--{part}", dest=part)
            group.add_argument(f"--{part}-file", dest=f"{part}_file")
        sub.add_argument("--count", type=int, default=1)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as error:
        return error.code if isinstance(error.code, int) else 2
    replace = args.command == "replace"
    key, value = ("old", "new") if replace else ("anchor", "text")
    try:
        target = path_guard.checked(args.file)
        raw = read_raw(target)
        edited, found = apply(raw, pick(args, key), pick(args, value), args.count, not replace)
    except (OSError, ValueError) as exc:
        print(f"edit failed: {exc}", file=sys.stderr)
        return 1
    with target.open("w", encoding="utf-8", newline="") as handle:
        handle.write(edited)
    print(f"{args.file}: {found} replacement(s), {len(edited.splitlines())} lines")
    return 0


if __name__ == "__main__":
    sys.exit(main())
