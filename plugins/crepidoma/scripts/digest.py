#!/usr/bin/env python3
"""Qualify long text before it reaches the main thread (stdlib only).

Reads FILE or stdin and prints at most 20 lines and --max-bytes (1 KB). Without --grep and
--tail the body depends on the kind (digest_kinds.py): Markdown headings, code definitions,
log FAIL/ERROR/panic/Traceback lines, else the first and last 5 lines, each with its line
number where it is a match. With either flag:
`lines <n> bytes <n>`, up to 6 distinct lines matching --grep, then the last
--tail lines, each cut to 160 characters. Exit code is always 0.

Usage:
  python digest.py build.log
  some-command 2>&1 | python digest.py --tail 5
  python digest.py out.txt --grep "timeout|refused" --max-bytes 600

Runs from the plugin scripts folder (bin/digest, `task repo:digest`), so it may import
its sibling digest_kinds and nothing outside the standard library.
"""

import argparse
import re
import sys
from pathlib import Path

import digest_kinds

DEFAULT_GREP = r"error|fail|exception|traceback|warn|denied"
MAX_LINES = 20
MAX_MATCHES = 6
LINE_WIDTH = 160


def cut(line: str) -> str:
    line = line.rstrip("\r\n")
    return line if len(line) <= LINE_WIDTH else line[: LINE_WIDTH - 3] + "..."


def digest(text: str, grep: str, tail: int, max_bytes: int, size: int | None = None) -> str:
    lines = text.splitlines()
    size = len(text.encode("utf-8", "replace")) if size is None else size
    out = [f"lines {len(lines)} bytes {size}"]
    try:
        pattern = re.compile(grep, re.IGNORECASE)
    except re.error:
        pattern = re.compile(re.escape(grep), re.IGNORECASE)
    seen: set[str] = set()
    for line in lines:
        if len(seen) >= MAX_MATCHES:
            break
        shown = cut(line)
        if shown not in seen and pattern.search(line):
            seen.add(shown)
            out.append(shown)
    tail = max(0, min(tail, MAX_LINES - len(out)))
    if tail:
        out.extend(cut(line) for line in lines[-tail:])
    return clamp(out, max_bytes)


def clamp(out: list[str], max_bytes: int) -> str:
    """Join with newlines, hard-capped at max_bytes, dropping whole lines first."""
    out = out[:MAX_LINES]
    while out and len("\n".join(out).encode("utf-8")) > max_bytes:
        if len(out) == 1:
            return out[0].encode("utf-8")[:max_bytes].decode("utf-8", "ignore")
        out.pop()
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print a bounded digest of a file or stdin.")
    parser.add_argument("file", nargs="?", help="file to read; stdin when omitted")
    parser.add_argument("--grep", default=None, help="regex for notable lines")
    parser.add_argument("--tail", type=int, default=None, help="trailing lines to show")
    parser.add_argument("--max-bytes", type=int, default=1024, help="hard output cap")
    args = parser.parse_args(argv)
    try:
        raw = Path(args.file).read_bytes() if args.file else sys.stdin.buffer.read()
    except OSError as error:
        print(f"digest: {error}")
        return 0
    text = raw.decode("utf-8", "replace")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")  # narrow consoles (cp1250) must not crash
    if args.grep is None and args.tail is None:
        lines = text.splitlines()
        head = f"lines {len(lines)} bytes {len(raw)}"
        body = digest_kinds.body(args.file or "", lines)
        print(clamp([head, *(cut(x) for x in body)], args.max_bytes))
        return 0
    grep = DEFAULT_GREP if args.grep is None else args.grep
    tail = 12 if args.tail is None else args.tail
    print(digest(text, grep, tail, args.max_bytes, size=len(raw)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
