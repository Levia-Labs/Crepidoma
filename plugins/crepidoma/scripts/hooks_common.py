"""Shared by every hook module: the project root, hook state, the payload and a refusal."""

import contextlib
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import NamedTuple

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd())


def state_dir(root: Path) -> Path:
    """Where hook state lives: the git dir (worktrees and submodules use a `.git` file),
    else a per-project temp dir so a non-git project never gets a stray `.git/`."""
    dot = root / ".git"
    if dot.is_dir():
        return dot
    with contextlib.suppress(OSError):
        text = dot.read_text(encoding="utf-8").strip()
        if text.startswith("gitdir:"):
            target = Path(text.removeprefix("gitdir:").strip())
            return target if target.is_absolute() else (root / target).resolve()
    key = hashlib.sha256(str(root.resolve()).encode("utf-8")).hexdigest()[:12]
    # Per-user, not the shared temp dir, so another account cannot plant state.
    cache = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".cache")
    return cache / "crepidoma" / key


STATE = state_dir(ROOT)


class Gate(NamedTuple):
    marker: Path
    # A path fragment the edited file must contain; "" accepts any path.
    watched: str
    suffixes: tuple[str, ...]
    tasks: tuple[str, ...]
    # Lines that name a finding, so the block reason stays short.
    hints: tuple[str, ...]
    skip: tuple[str, ...]


def payload() -> dict:
    try:
        data = json.load(sys.stdin)
    except (ValueError, OSError, AttributeError):
        return {}
    return data if isinstance(data, dict) else {}


def tool_input(event: dict) -> dict:
    value = event.get("tool_input")
    return value if isinstance(value, dict) else {}


def deny(reason: str) -> int:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    return 0


def opted_in() -> bool:
    """True when the project's committed settings enable crepidoma.

    Hooks run project code (task gates, graphify, a budget script) only after this
    opt-in, so a user-scope install never executes code from an untrusted checkout.
    """
    try:
        settings = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
        plugins = settings.get("enabledPlugins") or {}
    except (OSError, ValueError, AttributeError):
        return False
    return any(key.startswith("crepidoma@") and value is True for key, value in plugins.items())
