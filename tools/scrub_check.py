"""Fail when files carry local paths, emails, tokens or denylisted names.

Usage: scrub_check.py [--denylist FILE] PATH...
Prints `path:line: rule` per hit; exit 1 on any hit, 0 when clean.
A line containing `scrub:allow` is skipped. Undecodable files are skipped.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

RULES: dict[str, re.Pattern[str]] = {
    "windows-user-path": re.compile(r"\b[A-Za-z]:[\\/]+Users[\\/]+\w", re.IGNORECASE),
    "local-projects-path": re.compile(r"\b[A-Za-z]:[\\/]+Projects\b", re.IGNORECASE),
    "posix-home-path": re.compile(r"(?<![\w.~])/(?:home|Users)/\w"),
    "email": re.compile(r"\b[\w.%+-]+@[\w-]+(?:\.[\w-]+)*\.[A-Za-z]{2,}\b"),
    "token": re.compile(
        r"sk-ant-[\w-]{20,}|gh[pousr]_\w{30,}|github_pat_\w{30,}|AKIA[0-9A-Z]{16}"
        r"|-----BEGIN [A-Z ]*PRIVATE KEY-----"
    ),
}
ALLOWED_EMAILS = {"noreply@anthropic.com", "git@github.com"}
ALLOWED_EMAIL_SUFFIXES = ("@users.noreply.github.com", "@example.com")
ALLOW_MARKER = "scrub:allow"


def allowed_email(address: str) -> bool:
    address = address.lower()
    return address in ALLOWED_EMAILS or address.endswith(ALLOWED_EMAIL_SUFFIXES)


def load_denylist(path: Path | None) -> re.Pattern[str] | None:
    if path is None or not path.is_file():
        return None
    words = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    words = [word for word in words if word and not word.startswith("#")]
    if not words:
        return None
    return re.compile(r"\b(?:" + "|".join(map(re.escape, words)) + r")\b", re.IGNORECASE)


def scan_text(text: str, deny: re.Pattern[str] | None) -> list[tuple[int, str]]:
    hits: list[tuple[int, str]] = []
    for number, line in enumerate(text.splitlines(), 1):
        if ALLOW_MARKER in line:
            continue
        for rule, pattern in RULES.items():
            matches = [m.group() for m in pattern.finditer(line)]
            if rule == "email":
                matches = [m for m in matches if not allowed_email(m)]
            if matches:
                hits.append((number, rule))
        if deny is not None and deny.search(line):
            hits.append((number, "denylisted-name"))
    return hits


def scan_file(path: Path, deny: re.Pattern[str] | None) -> list[tuple[int, str]]:
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    return scan_text(text, deny)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--denylist", type=Path, default=Path(".scrub-denylist"))
    parser.add_argument("paths", nargs="*", type=Path)
    args = parser.parse_args(argv)
    deny = load_denylist(args.denylist)
    found = 0
    for path in args.paths:
        if not path.is_file():
            continue
        for number, rule in scan_file(path, deny):
            print(f"{path.as_posix()}:{number}: {rule}")
            found += 1
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())
