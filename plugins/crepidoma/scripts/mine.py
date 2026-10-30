#!/usr/bin/env python3
"""Mine every Claude Code project folder in one call (stdlib only).

Per project slug folder under the transcripts root it writes `<out>/<slug>.txt` with the session
spend summary (spend.py), repeated commands and repeated inline scripts (history.py). The main
output is one line per project, ranked by total tokens, at most 20 lines, then `reports <out>`.

Usage:
  python mine.py [--root DIR] [--out DIR] [--top N]

Row: `slug  sessions  tokens  cost  top-command (count)`. Default root is `~/.claude/projects`;
default out is a new temp dir. Exit codes: 0 ok, 1 no project folders, 2 usage error.
"""

import argparse
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import history
import spend

MAX_ROWS = 19  # plus the final `reports` line: 20 lines in all
SECTION_ROWS = 20


@dataclass
class Summary:
    slug: str
    sessions: int
    tokens: int
    cost: float
    top_command: str
    top_count: int


def format_row(summary: Summary) -> str:
    return (
        f"{summary.slug}  {summary.sessions}  {summary.tokens}  ${summary.cost:.2f}  "
        f"{summary.top_command} ({summary.top_count})"
    ).replace(" (0)", "")


def summarise(folder: Path) -> tuple[Summary, str]:
    """Summary row and the text report for one project slug folder."""
    sessions, agents = spend.load(folder, "")
    runs = sessions + agents
    tokens = sum(run.tokens() for run in runs)
    cost = sum(run.cost() for run in runs)
    commands = history.rank((history.normalise(c) for c in history.shell_commands(folder)), 1)
    inline = history.rank(
        (history.normalise(c) for c in history.shell_commands(folder) if history.is_inline(c)), 2
    )
    top, count = commands[0] if commands else ("-", 0)
    summary = Summary(folder.name, len(sessions), tokens, cost, top, count)
    report = "\n".join(
        [
            f"# {folder.name}",
            f"sessions {summary.sessions}  tokens {tokens}  cost ${cost:.2f}",
            "",
            "## repeated commands",
            *section([r for r in commands if r[1] >= 2]),
            "",
            "## repeated inline scripts",
            *section(inline),
            "",
        ]
    )
    return summary, report


def section(rows: list[tuple[str, int]]) -> list[str]:
    lines = [f"{n:5d}  {text[: history.TEXT_WIDTH]}" for text, n in rows[:SECTION_ROWS]]
    return lines or ["none"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Mine every Claude Code project folder.")
    parser.add_argument("--root", type=Path, help="transcripts root; default ~/.claude/projects")
    parser.add_argument("--out", type=Path, help="report folder; default a new temp dir")
    parser.add_argument("--top", type=int, default=MAX_ROWS, help=f"rows (max {MAX_ROWS})")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root or Path.home() / ".claude" / "projects"
    folders = sorted(p for p in root.iterdir() if p.is_dir()) if root.is_dir() else []
    if not folders:
        print(f"mine: no project folders at {root}")
        return 1
    out = args.out or Path(tempfile.mkdtemp(prefix="claude-mine-"))
    out.mkdir(parents=True, exist_ok=True)
    summaries = []
    for folder in folders:
        summary, report = summarise(folder)
        (out / f"{folder.name}.txt").write_text(report, encoding="utf-8", newline="\n")
        summaries.append(summary)
    summaries.sort(key=lambda s: (-s.tokens, s.slug))
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    for summary in summaries[: max(1, min(args.top, MAX_ROWS))]:
        print(format_row(summary))
    print(f"reports {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
