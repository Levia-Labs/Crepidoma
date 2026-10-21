"""Agent dispatch policy and the lane ledger: PreToolUse, SubagentStart, SubagentStop."""

import contextlib
import json
import os
import re
import time
from collections.abc import Iterator
from pathlib import Path

from hooks_budget import budget_refusal
from hooks_common import ROOT, STATE, deny, tool_input

PLUGIN_AGENTS = Path(__file__).resolve().parent.parent / "agents"


AGENT_TOOLS = ("Agent", "Task")
# No subagent_type means general-purpose. These read freely and relay what they read.
CATCH_ALL = frozenset({"", "general-purpose", "claude", "fork", "Explore", "Plan"})
MODELS = frozenset({"sonnet", "haiku"})
MAX_AGENTS = 6
PENDING_SECONDS = 120
# A lane that crashed never says finished. Past this age it stops holding a slot.
RUNNING_SECONDS = 4 * 3600
LEDGER = STATE / "claude-lanes.json"
LOCK_TRIES = 50
LOCK_STALE_SECONDS = 10


def defined_model(agent_type: str) -> str:
    """The `model:` an agent definition declares, from the project or this plugin."""
    name = agent_type.rsplit(":", 1)[-1]
    if not re.fullmatch(r"[\w.-]+", name):
        return ""
    for folder in (ROOT / ".claude" / "agents", PLUGIN_AGENTS):
        try:
            text = (folder / f"{name}.md").read_text(encoding="utf-8")
        except OSError:
            continue
        match = re.search(r"^model:\s*(\S+)", text, re.MULTILINE)
        return match.group(1) if match else ""
    return ""


def model_allowed(model: str) -> bool:
    return model in MODELS or bool(re.fullmatch(r"claude-(?:sonnet|haiku)-[\w.-]+", model))


def agent_refusal(arguments: dict) -> str | None:
    default = os.environ.get("CLAUDE_CODE_SUBAGENT_MODEL", "").strip()
    if default and not model_allowed(default):
        return (
            f"CLAUDE_CODE_SUBAGENT_MODEL is '{default}'. Set it to 'sonnet' or 'haiku' (or unset "
            "it); subagents never run on Opus."
        )
    kind = str(arguments.get("subagent_type") or "").strip()
    if kind in CATCH_ALL:
        return (
            f"Agent type '{kind or 'general-purpose'}' is a generic catch-all and is refused: "
            "it reads files and relays their content. Dispatch a named single-job agent from "
            ".claude/agents/ or a plugin that calls tools and returns a receipt; if none "
            "fits, write one first."
        )
    model = str(arguments.get("model") or defined_model(kind)).strip()
    if not model_allowed(model):
        return (
            f"Agent '{kind}' would run on '{model or 'the orchestrator model'}'. Only the main "
            "thread runs on Opus. Pass model 'sonnet' (work) or 'haiku' (grep, read, small "
            "lookups), or declare one in the agent definition."
        )
    return None


def cap_reason(count: int) -> str:
    return (
        f"{count} agents are already running or starting; the limit is {MAX_AGENTS}. "
        "Wait for one to finish before dispatching another."
    )


def running_agents(transcript: str, now: float) -> int:
    """Agents of this session still running, from the meta file the harness writes per agent.

    Agents dispatched in one message are checked before any writes its file; the ledger
    covers that gap.
    """
    if not transcript:
        return 0
    count = 0
    for meta in (Path(transcript).with_suffix("") / "subagents").glob("*.meta.json"):
        try:
            finished = json.loads(meta.read_text(encoding="utf-8")).get("finished")
            age = now - meta.stat().st_mtime
        except (OSError, ValueError, AttributeError):
            continue
        if not finished and age < RUNNING_SECONDS:
            count += 1
    return count


def load_ledger(now: float) -> dict:
    try:
        state = json.loads(LEDGER.read_text(encoding="utf-8"))
        running = {str(key): float(at) for key, at in state["running"].items()}
        pending = {str(key): float(at) for key, at in state["pending"].items()}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return {"running": {}, "pending": {}}
    return {
        "running": {key: at for key, at in running.items() if now - at < RUNNING_SECONDS},
        "pending": {key: at for key, at in pending.items() if now - at < PENDING_SECONDS},
    }


@contextlib.contextmanager
def locked_ledger() -> Iterator[dict]:
    """The lane ledger, read and written back under a lock file: parallel hooks race."""
    lock = LEDGER.with_suffix(".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    handle = None
    for _ in range(LOCK_TRIES):
        try:
            handle = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            # A lock older than a few seconds belongs to a killed hook.
            with contextlib.suppress(OSError):
                if time.time() - lock.stat().st_mtime > LOCK_STALE_SECONDS:
                    lock.unlink()
            time.sleep(0.05)
    try:
        state = load_ledger(time.time())
        yield state
        LEDGER.write_text(json.dumps(state), encoding="utf-8")
    finally:
        if handle is not None:
            os.close(handle)
            with contextlib.suppress(OSError):
                lock.unlink()


def pre_tool_use(event: dict) -> int:
    if event.get("tool_name") not in AGENT_TOOLS:
        return 0

    reason = agent_refusal(tool_input(event))
    if reason:
        return deny(reason)

    running = running_agents(str(event.get("transcript_path") or ""), time.time())
    if running >= MAX_AGENTS:
        return deny(cap_reason(running))

    reason = budget_refusal()
    if reason:
        return deny(reason)

    # The ledger fails open: an unwritable ledger is not a reason to block.
    with contextlib.suppress(OSError), locked_ledger() as state:
        live = len(state["running"]) + len(state["pending"])
        if live >= MAX_AGENTS:
            return deny(cap_reason(live))
        state["pending"][str(event.get("tool_use_id") or time.time())] = time.time()
    return 0


def subagent_start(event: dict) -> int:
    agent = str(event.get("agent_id") or f"unknown-{time.time()}")
    with contextlib.suppress(OSError), locked_ledger() as state:
        if state["pending"]:
            del state["pending"][min(state["pending"], key=state["pending"].__getitem__)]
        state["running"][agent] = time.time()
    return 0


def subagent_stop(event: dict) -> int:
    with contextlib.suppress(OSError), locked_ledger() as state:
        state["running"].pop(str(event.get("agent_id") or ""), None)
    return 0
