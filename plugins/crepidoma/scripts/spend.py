#!/usr/bin/env python3
"""Audit where Claude Code session transcripts spent tokens and money (stdlib only).

Reads `~/.claude/projects/<project-slug>/*.jsonl` (plus `<session>/subagents/agent-*.jsonl`).
Default project is the slug of `CLAUDE_PROJECT_DIR` or the cwd; `--dir` overrides the folder.
Output is top-N (`--top`, default 10) and never exceeds 20 lines.

Usage:
  python spend.py sessions [--last N]     # id8, date, tokens, cost estimate
  python spend.py tools [--session ID]    # tool name, calls, bytes returned
  python spend.py reads [--session ID]    # files read by bytes (Read, cat/head/tail/sed)
  python spend.py calls [--session ID]    # largest single tool results: tool, input, bytes
  python spend.py agents [--session ID]   # subagent runs: type, model, tokens
  # ID = session prefix, SESSION/AGENT (as `agents` prints it) or agent id suffix: that agent only
  python spend.py cost [--session ID]     # totals per model
  python spend.py cost --dir PATH/TO/TRANSCRIPTS
"""

import argparse
import json
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from spend_parse import bash_read_files, scan  # noqa: F401  (bash_read_files re-exported)

MAX_LINES = 20
DEFAULT_TOP = 10

# EDITABLE: USD per million tokens, keyed by model family (substring of the model id).
# Fields: input, output, cache_read, cache_write. Update when prices change.
PRICES: dict[str, dict[str, float]] = {
    "opus": {"input": 5.0, "output": 25.0, "cache_read": 0.50, "cache_write": 6.25},
    "sonnet": {"input": 3.0, "output": 15.0, "cache_read": 0.30, "cache_write": 3.75},
    "haiku": {"input": 1.0, "output": 5.0, "cache_read": 0.10, "cache_write": 1.25},
}
FIELDS = ("input", "output", "cache_read", "cache_write")
USAGE_KEYS = {
    "input": "input_tokens",
    "output": "output_tokens",
    "cache_read": "cache_read_input_tokens",
    "cache_write": "cache_creation_input_tokens",
}


def project_slug(path: Path) -> str:
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


def default_dir() -> Path:
    project = os.environ.get("CLAUDE_PROJECT_DIR") or str(Path.cwd())
    return Path.home() / ".claude" / "projects" / project_slug(Path(project))


@dataclass
class Run:
    """One transcript file: a session or a subagent."""

    name: str
    date: str = ""
    agent_type: str = ""
    usage: dict[str, Counter] = field(default_factory=dict)
    tool_calls: Counter = field(default_factory=Counter)
    tool_bytes: Counter = field(default_factory=Counter)
    read_bytes: Counter = field(default_factory=Counter)
    calls: list[tuple[str, str, int]] = field(default_factory=list)  # tool, input, bytes

    def add_usage(self, model: str, usage: dict) -> None:
        bucket = self.usage.setdefault(model, Counter())
        for key, source in USAGE_KEYS.items():
            value = usage.get(source, 0)
            bucket[key] += value if isinstance(value, int) else 0

    def tokens(self) -> int:
        return sum(sum(b.values()) for b in self.usage.values())

    def cost(self) -> float:
        return sum(model_cost(m, b) for m, b in self.usage.items())

    def main_model(self) -> str:
        if not self.usage:
            return "?"
        return max(self.usage, key=lambda m: sum(self.usage[m].values()))


def model_cost(model: str, bucket: Counter) -> float:
    for family, price in PRICES.items():
        if family in model.lower():
            return sum(bucket[f] * price[f] for f in FIELDS) / 1_000_000
    return 0.0


def parse(path: Path, name: str) -> Run:
    run = Run(name=name)
    scan(path, run)
    return run


def load_agent(file: Path, transcript: Path) -> Run:
    run = parse(file, f"{transcript.stem[:8]}/{file.stem[-8:]}")
    try:
        meta = json.loads(file.with_suffix(".meta.json").read_text(encoding="utf-8"))
        run.agent_type = str(meta.get("agentType", "?"))
    except (OSError, ValueError, AttributeError):
        run.agent_type = "?"
    return run


def load(folder: Path, session: str, with_agents: bool = True) -> tuple[list[Run], list[Run]]:
    """`session`: session prefix, `<session>/<agent>`, or an agent id suffix (agent only)."""
    sess, _, agent = session.partition("/")
    transcripts = sorted(folder.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    chosen = [t for t in transcripts if t.stem.startswith(sess)]
    if not agent and sess and not chosen:  # bare id matching no session: an agent suffix
        chosen, agent = transcripts, sess
    agent = agent.removeprefix("agent-")
    sessions: list[Run] = []
    agents: list[Run] = []
    for transcript in chosen:
        if not agent:
            sessions.append(parse(transcript, transcript.stem))
        if not with_agents and not agent:
            continue
        for file in sorted((folder / transcript.stem / "subagents").glob("agent-*.jsonl")):
            if file.stem.removeprefix("agent-").endswith(agent):
                agents.append(load_agent(file, transcript))
    return sessions, agents


def merged(sessions: list[Run], agents: list[Run]) -> list[Run]:
    return sessions + agents


def clip(lines: list[str]) -> list[str]:
    if len(lines) > MAX_LINES:
        lines = [*lines[: MAX_LINES - 1], f"... {len(lines) - MAX_LINES + 1} more"]
    return lines


def table(header: str, rows: list[str], total: str, top: int) -> list[str]:
    top = max(1, min(top, MAX_LINES - 2))
    return clip([header, *rows[:top], total])


def cmd_sessions(folder: Path, args: argparse.Namespace) -> list[str]:
    sessions, agents = load(folder, "")
    by_prefix: dict[str, list[Run]] = {}
    for agent in agents:
        by_prefix.setdefault(agent.name.split("/")[0], []).append(agent)
    rows = []
    for run in sessions:
        group = [run, *by_prefix.get(run.name[:8], [])]
        tokens = sum(r.tokens() for r in group)
        cost = sum(r.cost() for r in group)
        rows.append((run.date, f"{run.name[:8]} {run.date} {tokens:>12,} tok  ${cost:>8.2f}", cost))
    rows.sort(key=lambda r: r[0])
    last = args.last if args.last else args.top
    chosen = rows[-last:]
    total = sum(r[2] for r in chosen)
    return table(
        f"sessions {len(chosen)}/{len(rows)}",
        [r[1] for r in chosen],
        f"total ${total:.2f}",
        last,
    )


def cmd_tools(folder: Path, args: argparse.Namespace) -> list[str]:
    sessions, agents = load(folder, args.session or "")
    calls: Counter = Counter()
    size: Counter = Counter()
    for run in merged(sessions, agents):
        calls.update(run.tool_calls)
        size.update(run.tool_bytes)
    ranked = sorted(set(calls) | set(size), key=lambda t: size[t], reverse=True)
    rows = [f"{t:<24} {calls[t]:>6} calls {size[t]:>12,} B" for t in ranked]
    return table("tool calls bytes_returned", rows, f"total {sum(size.values()):,} B", args.top)


def cmd_reads(folder: Path, args: argparse.Namespace) -> list[str]:
    sessions, agents = load(folder, args.session or "")
    size: Counter = Counter()
    for run in merged(sessions, agents):
        size.update(run.read_bytes)
    rows = [f"{b:>10,} B {f[-90:]}" for f, b in size.most_common()]
    return table("files read by bytes", rows, f"total {sum(size.values()):,} B", args.top)


def cmd_calls(folder: Path, args: argparse.Namespace) -> list[str]:
    sessions, agents = load(folder, args.session or "")
    calls = [c for run in merged(sessions, agents) for c in run.calls]
    calls.sort(key=lambda c: c[2], reverse=True)
    rows = [f"{b:>10,} B {t:<10} {s}" for t, s, b in calls]
    return table("largest tool results", rows, f"calls {len(calls)}", args.top)


def cmd_agents(folder: Path, args: argparse.Namespace) -> list[str]:
    _, agents = load(folder, args.session or "")
    ranked = sorted(agents, key=lambda a: a.tokens(), reverse=True)
    rows = [
        f"{a.name:<18} {a.agent_type[:20]:<20} {a.main_model()[:24]:<24} {a.tokens():>11,} tok"
        for a in ranked
    ]
    total = f"agents {len(agents)} tokens {sum(a.tokens() for a in agents):,}"
    return table("agent type model tokens", rows, total, args.top)


def cmd_cost(folder: Path, args: argparse.Namespace) -> list[str]:
    sessions, agents = load(folder, args.session or "")
    totals: dict[str, Counter] = {}
    for run in merged(sessions, agents):
        for model, bucket in run.usage.items():
            totals.setdefault(model, Counter()).update(bucket)
    ranked = sorted(totals, key=lambda m: model_cost(m, totals[m]), reverse=True)
    rows = []
    for model in ranked:
        b = totals[model]
        priced = "" if any(f in model.lower() for f in PRICES) else " (no price)"
        rows.append(
            f"{model[:28]:<28} in {b['input']:,} out {b['output']:,} "
            f"cr {b['cache_read']:,} cw {b['cache_write']:,} "
            f"${model_cost(model, b):.2f}{priced}"
        )
    total = sum(model_cost(m, b) for m, b in totals.items())
    return table(
        "cost per model (PRICES editable in spend.py)", rows, f"total ${total:.2f}", args.top
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Transcript spend audit.")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--dir", type=Path, help="transcripts folder (default: cwd project)")
    common.add_argument("--top", type=int, default=DEFAULT_TOP, help="rows (default 10)")
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("sessions", parents=[common], help="one line per session")
    one.add_argument("--last", type=int, default=0, help="only the last N sessions")
    for name in ("tools", "reads", "calls", "agents", "cost"):
        p = sub.add_parser(name, parents=[common])
        p.add_argument("--session", help="session prefix, SESSION/AGENT, or agent id suffix")
    return parser


COMMANDS = {
    "sessions": cmd_sessions,
    "tools": cmd_tools,
    "reads": cmd_reads,
    "calls": cmd_calls,
    "agents": cmd_agents,
    "cost": cmd_cost,
}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    folder = args.dir or default_dir()
    if not folder.is_dir():
        print(f"no transcripts folder: {folder}", file=sys.stderr)
        return 2
    print("\n".join(COMMANDS[args.command](folder, args)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
