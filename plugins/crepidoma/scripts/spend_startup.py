"""`spend.py startup`: per-subagent startup cost (stdlib only). Not a command by itself.

One row per subagent: type, model, first-turn context tokens (input + cache_creation +
cache_read of the first assistant message) and the char size of each startup attachment
(records before that first assistant message), plus a totals line.
"""

import argparse
import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

ATTACHMENTS = {
    "hook_additional_context": ("hook", "content"),
    "instructions": ("instr", None),
    "mcp_instructions_delta": ("mcp", None),
    "prompt_snapshot": ("prompt", "systemPrompt"),
    "session_context": ("sess", None),
    "environment": ("env", None),
}
LATE = "mcp_instructions_delta"
USAGE = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
MAX_LINES = 20


@dataclass
class StartupRow:
    name: str
    agent_type: str
    model: str = "?"
    tokens: int = 0
    sizes: Counter = field(default_factory=Counter)


def first_turn_tokens(usage: dict) -> int:
    return sum(int(usage.get(key) or 0) for key in USAGE)


def attachment_size(att: dict) -> int:
    """Chars of the attachment payload as JSON (prompt/hook: their content field only)."""
    field_name = ATTACHMENTS[att["type"]][1]
    if field_name:
        return len(json.dumps(att.get(field_name)))
    return len(json.dumps({k: v for k, v in att.items() if k != "type"}))


def startup_row(path: Path, name: str, agent_type: str) -> StartupRow:
    row = StartupRow(name, agent_type)
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return row
    turns = 0
    for line in lines:
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if not isinstance(entry, dict):
            continue
        att = entry.get("attachment")
        if entry.get("type") == "attachment" and isinstance(att, dict):
            kind = att.get("type")
            # the MCP delta is logged after the first assistant message, with its tool results
            if kind in ATTACHMENTS and (turns == 0 or kind == LATE):
                row.sizes[kind] += attachment_size(att)
            continue
        msg = entry.get("message")
        if entry.get("type") == "assistant" and isinstance(msg, dict):
            turns += 1
            if turns == 1:
                row.model = str(msg.get("model", "?"))
                usage = msg.get("usage")
                row.tokens = first_turn_tokens(usage) if isinstance(usage, dict) else 0
            else:
                break
    return row


def agent_files(folder: Path, session: str) -> list[tuple[Path, str]]:
    sess, _, agent = session.partition("/")
    agent = agent.removeprefix("agent-")
    found = []
    for transcript in sorted(folder.glob("*.jsonl"), key=lambda p: p.stat().st_mtime):
        if not transcript.stem.startswith(sess):
            continue
        for file in sorted((folder / transcript.stem / "subagents").glob("agent-*.jsonl")):
            if file.stem.removeprefix("agent-").endswith(agent):
                found.append((file, f"{transcript.stem[:8]}/{file.stem[-8:]}"))
    return found


def agent_type(file: Path) -> str:
    try:
        meta = json.loads(file.with_suffix(".meta.json").read_text(encoding="utf-8"))
        return str(meta.get("agentType", "?"))
    except (OSError, ValueError, AttributeError):
        return "?"


def cmd_startup(folder: Path, args: argparse.Namespace) -> list[str]:
    rows = [startup_row(f, n, agent_type(f)) for f, n in agent_files(folder, args.session or "")]
    rows.sort(key=lambda r: r.tokens, reverse=True)
    keys = [short for short, _ in ATTACHMENTS.values()]
    header = "agent type model first-turn-tok | chars: " + " ".join(keys)
    top = max(1, min(args.top, MAX_LINES - 3))
    out = [header]
    for r in rows[:top]:
        chars = " ".join(f"{r.sizes.get(att, 0):>6}" for att in ATTACHMENTS)
        out.append(
            f"{r.name:<18} {r.agent_type[:16]:<16} {r.model[:20]:<20} {r.tokens:>8,} | {chars}"
        )
    total: Counter = Counter()
    for r in rows:
        total.update(r.sizes)
    chars = " ".join(f"{total.get(att, 0):>6}" for att in ATTACHMENTS)
    first = sum(r.tokens for r in rows)
    out.append(f"agents {len(rows)} first-turn {first:,} tok | chars: {chars}")
    return out
