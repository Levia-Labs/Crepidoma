#!/usr/bin/env python3
"""Audit where Claude Code session transcripts spent tokens and money (stdlib only).

Reads `~/.claude/projects/<project-slug>/*.jsonl` (plus `<session>/subagents/agent-*.jsonl`).
Default project is the slug of `CLAUDE_PROJECT_DIR` or the cwd; `--dir` overrides the folder.
Output is top-N (`--top`, default 10) and never exceeds 20 lines.

Usage:
  python spend.py sessions [--last N]     # id8, date, tokens, cost estimate
  python spend.py tools [--session ID]    # tool name, calls, bytes returned
  python spend.py reads [--session ID]    # files read by bytes (Read, cat/head/tail/sed)
  python spend.py agents [--session ID]   # subagent runs: type, model, tokens
  python spend.py cost [--session ID]     # totals per model
  python spend.py cost --dir PATH/TO/TRANSCRIPTS
"""

import argparse
import json
import os
import re
import shlex
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

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
READ_COMMANDS = {"cat", "head", "tail", "sed"}


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


def blocks(entry: dict) -> list[dict]:
    message = entry.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    return [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []


def result_bytes(content: object) -> int:
    if isinstance(content, str):
        return len(content.encode("utf-8", "replace"))
    if isinstance(content, list):
        return sum(
            len(str(b.get("text", "")).encode("utf-8", "replace"))
            for b in content
            if isinstance(b, dict)
        )
    return 0


def bash_read_files(command: str) -> list[str]:
    """Files named by a cat/head/tail/sed invocation (first such command in the string)."""
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        tokens = command.split()
    for index, token in enumerate(tokens):
        if Path(token).name not in READ_COMMANDS:
            continue
        name = Path(token).name
        files: list[str] = []
        skip_script = name == "sed"
        for arg in tokens[index + 1 :]:
            if arg in {"|", "||", "&&", ";", ">", ">>", "2>&1"}:
                break
            if arg.startswith("-") or arg.isdigit():
                continue
            if skip_script:
                skip_script = False
                continue
            files.append(arg)
        return files
    return []


def parse(path: Path, name: str) -> Run:
    run = Run(name=name)
    seen: set[str] = set()
    pending: dict[str, tuple[str, list[str]]] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if not isinstance(entry, dict):
            continue
        if not run.date and isinstance(entry.get("timestamp"), str):
            run.date = entry["timestamp"][:10]
        message = entry.get("message")
        if isinstance(message, dict) and isinstance(message.get("usage"), dict):
            # One API response is split across entries sharing id and usage: count once.
            key = str(message.get("id") or entry.get("uuid") or len(seen))
            if key not in seen:
                seen.add(key)
                run.add_usage(str(message.get("model") or "?"), message["usage"])
        for block in blocks(entry):
            if block.get("type") == "tool_use":
                tool = str(block.get("name"))
                params = block.get("input") if isinstance(block.get("input"), dict) else {}
                files: list[str] = []
                if tool == "Read" and params.get("file_path"):
                    files = [str(params["file_path"])]
                elif tool == "Bash":
                    files = bash_read_files(str(params.get("command", "")))
                pending[str(block.get("id"))] = (tool, [f.replace("\\", "/") for f in files])
                run.tool_calls[tool] += 1
            elif block.get("type") == "tool_result":
                tool, files = pending.get(str(block.get("tool_use_id")), ("?", []))
                size = result_bytes(block.get("content"))
                run.tool_bytes[tool] += size
                for file in files:
                    run.read_bytes[file] += size // len(files)
    if not run.date:
        run.date = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")
    return run


def load(folder: Path, session: str, with_agents: bool = True) -> tuple[list[Run], list[Run]]:
    sessions: list[Run] = []
    agents: list[Run] = []
    for transcript in sorted(folder.glob("*.jsonl"), key=lambda p: p.stat().st_mtime):
        if session and not transcript.stem.startswith(session):
            continue
        sessions.append(parse(transcript, transcript.stem))
        if not with_agents:
            continue
        for file in sorted((folder / transcript.stem / "subagents").glob("agent-*.jsonl")):
            run = parse(file, f"{transcript.stem[:8]}/{file.stem[-8:]}")
            try:
                meta = json.loads(file.with_suffix(".meta.json").read_text(encoding="utf-8"))
                run.agent_type = str(meta.get("agentType", "?"))
            except (OSError, ValueError, AttributeError):
                run.agent_type = "?"
            agents.append(run)
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
    for name in ("tools", "reads", "agents", "cost"):
        p = sub.add_parser(name, parents=[common])
        p.add_argument("--session", help="session id prefix")
    return parser


COMMANDS = {
    "sessions": cmd_sessions,
    "tools": cmd_tools,
    "reads": cmd_reads,
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
