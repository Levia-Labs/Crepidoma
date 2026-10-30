# /// script
# requires-python = ">=3.12"
# dependencies = ["claude-agent-sdk"]
# ///
"""Run one plugin agent on API credits through the Claude Agent SDK.

Usage:
    uv run --script api_agent.py --agent NAME (--brief TEXT | --brief-file F)
        [--cwd DIR] [--model M] [--max-budget-usd 2.0] [--max-turns 60]

Needs ANTHROPIC_API_KEY. Subscription tokens are removed from the environment first.
Exit 0 ok, 1 no key or run error, 2 usage, 3 credit at or under the floor.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import api_balance

AGENTS_DIR = Path(__file__).resolve().parent.parent / "agents"
SCRUB = ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_AUTH_TOKEN")
DENY = ["Bash(git push*)", "Bash(gh pr merge*)", "Bash(git reset --hard*)"]
RECEIPT_MAX = 10


def parse_agent(text: str) -> tuple[dict[str, str], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text.strip()
    meta: dict[str, str] = {}
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return meta, "\n".join(lines[i + 1 :]).strip()
        key, sep, value = line.partition(":")
        if sep:
            meta[key.strip()] = value.strip()
    return {}, text.strip()


def load_agent(name: str, agents_dir: Path = AGENTS_DIR) -> dict:
    meta, body = parse_agent((agents_dir / f"{name}.md").read_text(encoding="utf-8"))
    tools = [t.strip() for t in meta.get("tools", "").split(",") if t.strip()]
    return {"tools": tools, "model": meta.get("model") or "sonnet", "prompt": body}


def scrub_env(env: dict[str, str]) -> None:
    for name in SCRUB:
        env.pop(name, None)


def receipt(result, remaining: float | None, tail: int = 5) -> list[str]:
    head = [
        f"subtype: {result.subtype}",
        f"turns: {result.num_turns}",
        f"cost: ${(result.total_cost_usd or 0):.4f}",
        "remaining: " + ("unknown" if remaining is None else f"${remaining:.2f}"),
    ]
    body = [ln for ln in (result.result or "").splitlines() if ln.strip()]
    keep = min(tail, RECEIPT_MAX - len(head))
    return head + (body[-keep:] if keep > 0 else [])


async def run_query(query: Callable, prompt: str, options):
    final = None
    async for message in query(prompt=prompt, options=options):
        if hasattr(message, "subtype") and hasattr(message, "total_cost_usd"):
            final = message
    return final


def build_options(agent: dict, args, options_cls: Callable, env: dict[str, str]):
    return options_cls(
        model=args.model or agent["model"],
        cwd=args.cwd,
        allowed_tools=agent["tools"],
        disallowed_tools=list(DENY),
        permission_mode="acceptEdits",
        max_turns=args.max_turns,
        max_budget_usd=args.max_budget_usd,
        system_prompt=agent["prompt"],
        setting_sources=["project"],
        env={"ANTHROPIC_API_KEY": env["ANTHROPIC_API_KEY"]},
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="api_agent", description=__doc__)
    parser.add_argument("--agent", required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--brief")
    group.add_argument("--brief-file")
    parser.add_argument("--cwd", default=str(Path.cwd()))
    parser.add_argument("--model")
    parser.add_argument("--max-budget-usd", type=float, default=2.0)
    parser.add_argument("--max-turns", type=int, default=60)
    return parser


def main(
    argv: list[str] | None = None,
    query: Callable | None = None,
    options_cls: Callable | None = None,
    agents_dir: Path = AGENTS_DIR,
    opener: Callable = urllib.request.urlopen,
) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    env = os.environ
    if not env.get("ANTHROPIC_API_KEY", "").strip():
        print("api run: ANTHROPIC_API_KEY unset", file=sys.stderr)
        return 1
    now = datetime.now(UTC)
    before = api_balance.estimate(env, opener, now.date(), now)
    if api_balance.exit_code(before) == 3:
        print("api run: credit at or under floor", file=sys.stderr)
        return 3
    try:
        agent = load_agent(args.agent, agents_dir)
        brief = args.brief or Path(args.brief_file).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"api run: {exc.strerror}: {exc.filename}", file=sys.stderr)
        return 2
    scrub_env(env)
    if query is None or options_cls is None:
        import claude_agent_sdk

        query = query or claude_agent_sdk.query
        options_cls = options_cls or claude_agent_sdk.ClaudeAgentOptions
    options = build_options(agent, args, options_cls, env)
    result = asyncio.run(run_query(query, brief, options))
    if result is None:
        print("api run: no result message", file=sys.stderr)
        return 1
    now = datetime.now(UTC)
    api_balance.append_ledger(
        api_balance.ledger_path(env),
        {
            "ts": now.isoformat(timespec="seconds"),
            "agent": args.agent,
            "model": args.model or agent["model"],
            "subtype": result.subtype,
            "turns": result.num_turns,
            "cost_usd": result.total_cost_usd or 0,
            "session_id": result.session_id,
            "cwd": args.cwd,
        },
    )
    after = api_balance.estimate(env, opener, now.date(), now)
    print("\n".join(receipt(result, after["left"] if after else None)))
    return 1 if result.is_error else 0


if __name__ == "__main__":
    sys.exit(main())
