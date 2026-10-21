"""The usage allowance: a cached reading and the refusal when a window is at the ceiling."""

import contextlib
import json
import subprocess
import sys
import time
from pathlib import Path

from hooks_common import ROOT, STATE, opted_in

CEILING = 95.0
USAGE_CACHE = STATE / "claude-usage.json"
# The usage endpoint answers 429 to a tight poll. One reading serves every check inside this.
CACHE_SECONDS = 60
BUDGET_SCRIPTS = ("tasks/claude/budget.py", "Tasks/claude/budget.py")
BUDGET_TIMEOUT = 30


def budget_script() -> Path | None:
    """The plugin's own budget.py: trusted code, so no project opt-in is needed."""
    bundled = Path(__file__).resolve().parent / "budget.py"
    if bundled.is_file():
        return bundled
    if not opted_in():
        return None
    return next((ROOT / name for name in BUDGET_SCRIPTS if (ROOT / name).is_file()), None)


def usage_reading() -> dict:
    """The allowance, from a cached reading where one is fresh enough to reuse.

    Unknown answers an empty dict: not knowing the allowance never blocks work.
    """
    with contextlib.suppress(OSError, ValueError, TypeError, AttributeError):
        cached = json.loads(USAGE_CACHE.read_text(encoding="utf-8"))
        age = time.time() - float(cached.get("read_at", 0))
        reading = cached.get("reading")
        if 0 <= age < CACHE_SECONDS and isinstance(reading, dict) and reading.get("ok"):
            return reading

    budget = budget_script()
    if budget is None:
        return {}
    try:
        result = subprocess.run(
            [sys.executable, str(budget), "--json", "--ceiling", str(CEILING)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            shell=False,
            check=False,
            timeout=BUDGET_TIMEOUT,
        )
        reading = json.loads(result.stdout)
    except (OSError, ValueError, TypeError, subprocess.SubprocessError):
        return {}
    if not isinstance(reading, dict) or not reading.get("ok"):
        return {}

    # A cache that cannot be written costs a reading, not a run.
    with contextlib.suppress(OSError):
        USAGE_CACHE.parent.mkdir(parents=True, exist_ok=True)
        USAGE_CACHE.write_text(
            json.dumps({"read_at": time.time(), "reading": reading}), encoding="utf-8"
        )
    return reading


def span(seconds: int) -> str:
    hours, rest = divmod(max(0, int(seconds)), 3600)
    return f"{hours}h {rest // 60}m" if hours else f"{rest // 60}m"


def budget_refusal() -> str | None:
    reading = usage_reading()
    if not reading.get("over_ceiling"):
        return None
    spent = ", ".join(
        f"{row.get('label')} at {row.get('utilization', 0):.0f}%"
        for row in reading.get("windows", [])
        if row.get("utilization", 0) >= CEILING
    )
    return (
        f"Usage is at the {CEILING:g}% ceiling ({spent}). Do not dispatch this agent: one "
        "started now dies mid-write and loses what it was holding.\n"
        "Write down where the work stands and resume in "
        f"{span(reading.get('wait_seconds', 0))} with `task claude:resume`."
    )
