"""Review helpers that keep big text out of the chat: write it to a file, print the path.

Usage:
  review_files.py diff BASE HEAD [PATH...]
  review_files.py relay REVIEW_FILE [--gate COMMAND]

`diff` writes log, stat and -U10 diff of BASE..HEAD to a unique temp file. `relay` turns
`severity | file:line | issue | fix` lines into a numbered fix list ending with the gate command.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

SEVERITIES = {"critical", "high", "important", "medium", "major", "low", "minor"}


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if result.returncode != 0:
        raise ValueError(result.stderr.strip() or f"git {args[0]} failed")
    return result.stdout


def write_temp(prefix: str, text: str) -> Path:
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="\n", prefix=prefix, suffix=".txt", delete=False
    ) as handle:
        handle.write(text)
    return Path(handle.name)


def diff(base: str, head: str, paths: list[str]) -> int:
    span = f"{base}..{head}"
    tail = ["--", *paths] if paths else []
    try:
        parts = [
            "== log ==\n" + git("log", "--oneline", span, *tail),
            "== stat ==\n" + git("diff", "--stat", span, *tail),
            "== diff ==\n" + git("diff", "-U10", span, *tail),
        ]
    except ValueError as exc:
        print(f"git failed: {exc}", file=sys.stderr)
        return 1
    text = "\n".join(parts)
    path = write_temp("review-diff-", text)
    print(f"{path} {len(text.splitlines())} lines")
    return 0


def fix_list(text: str, gate: str) -> list[str]:
    lines = []
    for raw in text.splitlines():
        parts = [part.strip() for part in raw.strip().lstrip("-*0123456789. ").split("|")]
        if len(parts) >= 4 and parts[0].lower() in SEVERITIES:
            fix = " | ".join(parts[3:])
            lines.append(f"{len(lines) + 1}. {parts[1]} | {parts[2]} | fix: {fix}")
    if lines and gate:
        lines.append(f"Gate: {gate}")
    return lines


def relay(review: Path, gate: str) -> int:
    try:
        lines = fix_list(review.read_text(encoding="utf-8"), gate)
    except OSError as exc:
        print(f"unreadable: {exc}", file=sys.stderr)
        return 1
    if not lines:
        print("no findings in the review file", file=sys.stderr)
        return 1
    path = write_temp("review-fixes-", "\n".join(lines) + "\n")
    print(f"{path} {len(lines)} lines")
    return 0


def main(argv: list[str]) -> int:
    if argv[:1] == ["diff"] and len(argv) >= 3:
        return diff(argv[1], argv[2], argv[3:])
    if argv[:1] == ["relay"] and len(argv) == 2:
        return relay(Path(argv[1]), "")
    if argv[:1] == ["relay"] and len(argv) == 4 and argv[2] == "--gate":
        return relay(Path(argv[1]), argv[3])
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
