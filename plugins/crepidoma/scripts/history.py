#!/usr/bin/env python3
"""Find repeated ad-hoc work in Claude Code history that should become a tool (stdlib only).

Subcommands read transcripts (`~/.claude/projects/<slug>/*.jsonl`) and the prompt log
(`~/.claude/history.jsonl`): `commands` lists normalised Bash/PowerShell commands repeated at
least --min times, `inline` lists interpreter one-liners and heredoc scripts, `prompts` lists
user prompts repeated across sessions or projects. Output is one `count  text` line per entry,
top 10 by default, never more than 20 lines or 1 KB; `--report FILE` writes every entry.

Usage:
  python history.py commands [--min 3] [--top 10] [--dir DIR] [--report FILE]
  python history.py inline [--min 1] [--dir DIR]
  python history.py prompts [--min 2] [--prompts FILE]
  python history.py sessions [--dir DIR]
  python history.py untasked [--min 3] [--top 10] [--dir DIR] [--root REPO]

`sessions` lists each transcript with its size; `untasked` is `commands` minus the ones that
already run a task defined in the Taskfiles under --root (default: the working directory).

Default transcript dir is the slug folder of the current project (`CLAUDE_PROJECT_DIR` or the
working directory); `--dir` may also be the whole `projects` folder. Exit codes: 0 ok, 1 no
source found, 2 usage error.
"""

import argparse
import json
import os
import re
import sys
from collections import Counter
from collections.abc import Iterator
from pathlib import Path

MAX_LINES = 20
MAX_BYTES = 1024
TEXT_WIDTH = 80
SHELL_TOOLS = ("Bash", "PowerShell")

HASH = re.compile(r"\b[0-9a-f]{7,40}\b")
PATH = re.compile(r"(?:[A-Za-z]:)?[\\/]?[\w.~-]+(?:[\\/][\w.~-]+)+[\\/]?")
NUMBER = re.compile(r"\b\d+(?:\.\d+)*\b")
INLINE = re.compile(
    r"\b(?:python3?|py|node|ruby|perl|php|pwsh|powershell)(?:\.exe)?\s+"
    r"(?:-[A-Za-z]+\s+)*-(?:c|e|E|Command)\b"
)
HEREDOC = re.compile(
    r"\b(?:python3?|py|node|ruby|perl|php|bash|sh|pwsh|powershell)(?:\.exe)?\b[^\n<]*<<-?\s*['\"]?\w+"
)


def normalise(text: str) -> str:
    """Collapse whitespace and replace hashes, paths and numbers with placeholders."""
    text = " ".join(text.split())
    text = PATH.sub("<path>", text)
    text = HASH.sub("<hash>", text)
    return NUMBER.sub("<n>", text)


def default_dir() -> Path:
    root = os.environ.get("CLAUDE_PROJECT_DIR") or str(Path.cwd())
    slug = re.sub(r"[^A-Za-z0-9]", "-", root)
    return Path.home() / ".claude" / "projects" / slug


def shell_commands(directory: Path) -> Iterator[str]:
    """Every Bash/PowerShell command in every transcript under directory."""
    for transcript in sorted(directory.rglob("*.jsonl")):
        with transcript.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if '"command"' not in line:
                    continue
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                message = entry.get("message") if isinstance(entry, dict) else None
                content = message.get("content") if isinstance(message, dict) else None
                if not isinstance(content, list):
                    continue
                for block in content:
                    if not isinstance(block, dict) or block.get("type") != "tool_use":
                        continue
                    if block.get("name") not in SHELL_TOOLS:
                        continue
                    command = (block.get("input") or {}).get("command")
                    if isinstance(command, str) and command.strip():
                        yield command


def prompt_texts(path: Path) -> Iterator[str]:
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            display = entry.get("display") if isinstance(entry, dict) else None
            if isinstance(display, str) and display.strip():
                yield display


def is_inline(command: str) -> bool:
    return bool(INLINE.search(command) or HEREDOC.search(command))


def rank(items: Iterator[str], minimum: int) -> list[tuple[str, int]]:
    counts = Counter(items)
    found = [(text, n) for text, n in counts.items() if n >= minimum]
    return sorted(found, key=lambda pair: (-pair[1], pair[0]))


def render(rows: list[tuple[str, int]], top: int, max_bytes: int = MAX_BYTES) -> str:
    """`count  text` lines, capped by top, MAX_LINES and max_bytes."""
    top = max(1, min(top, MAX_LINES))
    out = [f"{n:5d}  {text[:TEXT_WIDTH]}" for text, n in rows[:top]]
    while out and len("\n".join(out).encode("utf-8")) > max_bytes:
        out.pop()
    return "\n".join(out)


def task_names(root: Path) -> set[str]:
    """Every task name (bare and namespaced) defined by a .yml under taskfiles/ or tasks/."""
    names: set[str] = set()
    for folder in ("taskfiles", "tasks"):
        for taskfile in (root / folder).rglob("*.yml"):
            for line in taskfile.read_text(encoding="utf-8", errors="replace").splitlines():
                match = re.match(r"^  ([a-z][a-z0-9:_-]*):\s*$", line)
                if match:
                    names.add(match.group(1))
                    names.add(f"{taskfile.parent.name}:{match.group(1)}")
    return names


def untasked(commands: Iterator[str], root: Path) -> Iterator[str]:
    """Commands that are not a `task` call and whose second word names no known task."""
    known = task_names(root)
    for command in commands:
        words = command.split()
        if words and words[0] in ("task", "cd", "echo", "ls", "cat", "printf", "true"):
            continue
        if len(words) > 1 and words[1] in known:
            continue
        yield command


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Find repeated ad-hoc work in Claude history.")
    sub = parser.add_subparsers(dest="mode", required=True)
    listing = sub.add_parser("sessions", help="transcripts with their size")
    listing.add_argument("--dir", help="transcript dir; default current project slug")
    for name, minimum in (("commands", 3), ("inline", 1), ("prompts", 2), ("untasked", 3)):
        cmd = sub.add_parser(name)
        cmd.add_argument("--min", type=int, default=minimum, help="minimum repeat count")
        cmd.add_argument("--top", type=int, default=10, help=f"rows to show (max {MAX_LINES})")
        cmd.add_argument("--report", help="write every entry to this file")
        if name == "untasked":
            cmd.add_argument("--root", default=".", help="repo whose Taskfiles define the tasks")
        if name == "prompts":
            cmd.add_argument("--prompts", help="prompt log; default ~/.claude/history.jsonl")
        else:
            cmd.add_argument("--dir", help="transcript dir; default current project slug")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.mode == "sessions":
        source = Path(args.dir) if args.dir else default_dir()
        if not source.is_dir():
            print(f"history: no transcripts at {source}")
            return 1
        for transcript in sorted(source.rglob("*.jsonl")):
            print(f"{transcript.stat().st_size / 1_000_000:8.1f} MB  {transcript.name}")
        return 0
    if args.mode == "prompts":
        source = Path(args.prompts) if args.prompts else Path.home() / ".claude" / "history.jsonl"
        if not source.is_file():
            print(f"history: no prompt log at {source}")
            return 1
        texts = (normalise(p) for p in prompt_texts(source))
        rows = rank((t for t in texts if len(t) >= 8), args.min)
    else:
        source = Path(args.dir) if args.dir else default_dir()
        if not source.is_dir():
            print(f"history: no transcripts at {source}")
            return 1
        commands = shell_commands(source)
        if args.mode == "inline":
            rows = rank((normalise(c) for c in commands if is_inline(c)), args.min)
        elif args.mode == "untasked":
            rows = rank((normalise(c) for c in untasked(commands, Path(args.root))), args.min)
        else:
            rows = rank((normalise(c) for c in commands), args.min)
    if args.report:
        lines = [f"{n:5d}  {text}" for text, n in rows]
        Path(args.report).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    print(render(rows, args.top) or "none")
    return 0


if __name__ == "__main__":
    sys.exit(main())
