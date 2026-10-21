#!/usr/bin/env python3
"""Where this project's Claude sessions spent their tokens: the main loop or the subagents.

history.py counts the shell commands a session ran. This counts what the sessions cost, and
who in them paid: every subagent transcript under <session>/subagents/ is read with its
.meta.json, so a lane that read forty files to relay three lines shows up by name.

The figures are the API's own usage blocks, not estimates. "context" is every input token the
model processed (fresh, cache write and cache read) plus its output - the number a usage window
is charged against. "results" is the bytes of tool output fed back into the agent, "prompt"
and "reply" the bytes of brief going in and of report coming back to the main loop.

Usage:
  python3 agents.py                    # cost by agent type, then the costliest agents
  python3 agents.py --top 20           # more agents
  python3 agents.py --session 6585     # one session, by id prefix
  python3 agents.py --sessions         # per session: main loop versus subagents
  python3 agents.py --reads --top 30   # the files subagents read most
  python3 agents.py --json             # every agent, machine readable
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd())
SLUG = re.sub(r"[^A-Za-z0-9]", "-", str(ROOT))
TRANSCRIPTS = Path.home() / ".claude" / "projects" / SLUG


@dataclass
class Cost:
    context: int = 0
    output: int = 0
    turns: int = 0
    results: int = 0
    # A transcript opens on its brief and ends on its report, so both are read from the
    # agent's own file. The main loop's tool_result for a background agent is only a
    # "launched" notice; the report arrives later in a notification.
    prompt: int = 0
    reply: int = 0
    # The context of the first turn: system prompt, tool schemas, CLAUDE.md, skill listing and
    # brief. Every later turn re-reads it, so it is the floor each turn of the agent pays.
    base: int = 0
    # A plain dict: asdict() rebuilds a Counter from (key, value) pairs and counts the pairs.
    tools: dict[str, int] = field(default_factory=dict)


@dataclass
class Agent:
    session: str
    kind: str
    description: str
    model: str
    cost: Cost


def entries(path: Path):
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if isinstance(entry, dict):
            yield entry


def blocks(entry: dict) -> list[dict]:
    message = entry.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    return [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []


def size(content) -> int:
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        return sum(len(b.get("text", "")) for b in content if isinstance(b, dict))
    return 0


def cost_of(path: Path) -> Cost:
    cost = Cost()
    # One API response is written as several entries, one per content block, each carrying
    # the same usage. Counted once per message id, or a three-block reply bills three times.
    seen: set[str] = set()
    for entry in entries(path):
        message = entry.get("message")
        if not isinstance(message, dict):
            continue
        if entry.get("type") == "user" and not cost.prompt:
            cost.prompt = size(message.get("content"))
        text = 0
        for block in blocks(entry):
            if block.get("type") == "tool_use":
                name = str(block.get("name"))
                cost.tools[name] = cost.tools.get(name, 0) + 1
            elif block.get("type") == "tool_result":
                cost.results += size(block.get("content"))
            elif block.get("type") == "text" and entry.get("type") == "assistant":
                text += len(block.get("text", ""))
        if text:
            cost.reply = text
        usage = message.get("usage")
        key = str(message.get("id") or id(entry))
        if entry.get("type") != "assistant" or not isinstance(usage, dict) or key in seen:
            continue
        seen.add(key)
        cost.turns += 1
        output = int(usage.get("output_tokens") or 0)
        read = sum(
            int(usage.get(k) or 0)
            for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
        )
        cost.base = cost.base or read
        cost.output += output
        cost.context += output + read
    return cost


def agents(prefix: str = "") -> list[Agent]:
    found = []
    for session in sorted(TRANSCRIPTS.glob(f"{prefix}*.jsonl")):
        for transcript in sorted((session.with_suffix("") / "subagents").glob("agent-*.jsonl")):
            try:
                meta = json.loads(transcript.with_suffix(".meta.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                meta = {}
            found.append(
                Agent(
                    session=session.stem[:8],
                    kind=str(meta.get("agentType") or "?"),
                    description=str(meta.get("description") or ""),
                    model=str(meta.get("model") or ""),
                    cost=cost_of(transcript),
                )
            )
    return found


def k(tokens: int) -> str:
    return f"{tokens / 1000:,.0f}k"


def report(found: list[Agent], top: int) -> None:
    by_kind: dict[str, list[Agent]] = defaultdict(list)
    for agent in found:
        by_kind[agent.kind].append(agent)
    total = sum(a.cost.context for a in found)
    print(f"{len(found)} subagent(s), {k(total)} context tokens\n")
    print(f"{'agents':>6} {'context':>9} {'per agent':>10}  type")
    for kind, group in sorted(by_kind.items(), key=lambda kv: -sum(a.cost.context for a in kv[1])):
        spent = sum(a.cost.context for a in group)
        print(f"{len(group):6d} {k(spent):>9} {k(spent // len(group)):>10}  {kind}")

    header = f"{'context':>9} {'base':>5} {'turns':>5} {'results':>8} {'prompt':>6} {'reply':>6}"
    print(f"\n{header}  session  type / description")
    for agent in sorted(found, key=lambda a: -a.cost.context)[:top]:
        c = agent.cost
        print(
            f"{k(c.context):>9} {k(c.base):>5} {c.turns:5d} {c.results // 1024:6d}KB "
            f"{c.prompt:6d} {c.reply:6d}  {agent.session}  {agent.kind} / {agent.description[:50]}"
        )
        busiest = ", ".join(f"{n} {t}" for t, n in Counter(c.tools).most_common(4))
        print(f"{'':>47}{busiest}")


def relative(path: str) -> str:
    """The path under the project root when it is inside it, else as given."""
    flat = path.replace("\\", "/")
    root = str(ROOT).replace("\\", "/").rstrip("/") + "/"
    return flat[len(root) :] if flat.startswith(root) else flat


def reads(prefix: str, top: int) -> None:
    """The files subagents read most: each is a candidate for an outline or a query tool."""
    counts: Counter = Counter()
    for session in sorted(TRANSCRIPTS.glob(f"{prefix}*.jsonl")):
        for transcript in (session.with_suffix("") / "subagents").glob("agent-*.jsonl"):
            for entry in entries(transcript):
                for block in blocks(entry):
                    if block.get("type") == "tool_use" and block.get("name") == "Read":
                        path = str((block.get("input") or {}).get("file_path", ""))
                        counts[relative(path)] += 1
    for path, count in counts.most_common(top):
        print(f"{count:5d}  {path}")


def sessions(prefix: str) -> None:
    print(f"{'main':>9} {'agents':>9} {'n':>3}  session")
    for session in sorted(TRANSCRIPTS.glob(f"{prefix}*.jsonl")):
        main = cost_of(session).context
        subs = agents(session.stem)
        spent = sum(a.cost.context for a in subs)
        print(f"{k(main):>9} {k(spent):>9} {len(subs):3d}  {session.stem[:8]}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Subagent token cost, from the transcripts.")
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--session", default="", help="session id prefix")
    parser.add_argument("--sessions", action="store_true")
    parser.add_argument("--reads", action="store_true", help="files the subagents read most")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if not TRANSCRIPTS.is_dir():
        print(f"no transcripts under {TRANSCRIPTS}", file=sys.stderr)
        return 1
    if args.sessions:
        sessions(args.session)
        return 0
    if args.reads:
        reads(args.session, args.top)
        return 0

    found = agents(args.session)
    if args.json:
        print(json.dumps([asdict(a) for a in found]))
        return 0
    if not found:
        print("no subagent transcripts")
        return 0
    report(found, args.top)
    return 0


if __name__ == "__main__":
    sys.exit(main())
