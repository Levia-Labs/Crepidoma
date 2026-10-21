"""Quality gates: PostToolUse marks a gate dirty, Stop runs the dirty gates' tasks."""

import contextlib
import json
import os
import shutil
import subprocess
import sys

import rtk_route
from hooks_budget import CEILING, span, usage_reading
from hooks_common import ROOT, STATE, Gate, opted_in, tool_input

WATCHED_SUFFIXES = (
    ".yml",
    ".yaml",
    ".py",
    ".md",
    ".sh",
    ".toml",
    ".html",
    ".js",
    ".css",
    ".ts",
    ".tsx",
)
SKIP = ("graphify-out/", ".claude/skills/")
GATES = (Gate(STATE / "claude-dirty", "", WATCHED_SUFFIXES, ("validate",), (), SKIP),)

PROGRESS = rtk_route.NOISE
TAIL_LINES = 40
HINT_LINES = 10
# Only the last lines of a failed run decide whether the gate could not run at all: a real
# failure can quote a skip phrase earlier, in a test's captured output.
SKIP_TAIL = 3


# Reasons a gate could not run. None is a lint failure, and blocking on one walls the agent
# in behind something no edit can fix.
DID_NOT_RUN = (
    "not on PATH",
    "command not found",
    "precondition not met",
    "executable file not found",
    "Failed to spawn",
    "No module named pytest",
    "No module named 'hypothesis'",
    "does not exist",  # task: Task "validate" does not exist
    "No Taskfile found",
)


def relative(path: str) -> str:
    text = path.replace("\\", "/")
    root = ROOT.as_posix().lower()
    index = text.lower().find(root)
    if index >= 0:
        text = text[index + len(root) :]
    return text.lstrip("/")


def in_scope(path: str, gate: Gate | None = None) -> bool:
    gate = gate or GATES[0]
    text = relative(path)
    if not text.endswith(gate.suffixes) or gate.watched not in text:
        return False
    return not any(skip in text for skip in gate.skip)


def post_tool_use(event: dict) -> int:
    path = str(tool_input(event).get("file_path") or "")
    if not path or not opted_in():
        return 0
    for gate in GATES:
        if in_scope(path, gate):
            gate.marker.parent.mkdir(parents=True, exist_ok=True)
            gate.marker.touch()
    return 0


def run(*command: str) -> subprocess.CompletedProcess:
    command = rtk_route.wrap(command, ROOT)  # rtk filters project gates; which() needs no shell
    executable = shutil.which(command[0])
    missing = subprocess.CompletedProcess(
        command, 127, "", f"{command[0]}: executable file not found"
    )
    if executable is None:
        return missing
    try:
        return subprocess.run(
            [executable, *command[1:]],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            check=False,
        )
    except FileNotFoundError:
        return missing


def skip_reason(output: str) -> str | None:
    tail = [line for line in output.splitlines() if line.strip()][-SKIP_TAIL:]
    # A pytest FAILED/ERROR/"E   " line quotes the assertion: a real failure, never a skip.
    text = "\n".join(
        line for line in tail if not line.lstrip().startswith(("FAILED", "ERROR", "E "))
    )
    return next((reason for reason in DID_NOT_RUN if reason in text), None)


def failure(task: str, result: subprocess.CompletedProcess, hints: tuple[str, ...] = ()) -> str:
    lines = [
        line
        for line in (result.stdout + result.stderr).strip().splitlines()
        if line.strip() and not PROGRESS.match(line)
    ]
    findings = [line for line in lines if any(hint in line for hint in hints)][:HINT_LINES]
    return f"task {task} failed. Fix it before ending the turn:\n" + "\n".join(
        findings or lines[-TAIL_LINES:]
    )


def stop(event: dict, tasks: tuple[str, ...] = ()) -> int:
    # A blocked stop re-enters this hook once the agent replies. Without this the pair loops.
    if event.get("stop_hook_active") or not opted_in():
        return 0
    # A pillar with its own compile gate switches this one off via .claude/settings.json env.
    if os.environ.get("CREPIDOMA_STOP_GATE") == "off":
        return 0
    dirty = [gate._replace(tasks=tasks or gate.tasks) for gate in GATES if gate.marker.exists()]
    if not dirty:
        return 0

    for gate in dirty:
        for task in gate.tasks:
            result = run("task", task)
            if result.returncode == 0:
                continue
            reason = skip_reason(result.stdout + result.stderr)
            if reason is not None:
                message = (
                    f"Skipped task {task} - it could not run ({reason}). Install the "
                    "project's tools. The marker stays set, so validation happens on the "
                    "next turn that can run it."
                )
                print(json.dumps({"systemMessage": message}))
                return 0
            print(json.dumps({"decision": "block", "reason": failure(task, result, gate.hints)}))
            return 0
        gate.marker.unlink(missing_ok=True)

    # AST-only, no API cost. A missing graphify binary is not an error here.
    with contextlib.suppress(OSError):
        run("graphify", "update", ".", "--force")

    # Said rather than blocking: the ceiling stops new work, never a finishing turn.
    reading = usage_reading()
    if reading.get("over_ceiling"):
        print(
            f"Usage is at the {CEILING:g}% ceiling. Resume in "
            f"{span(reading.get('wait_seconds', 0))} with `task claude:resume`.",
            file=sys.stderr,
        )
    return 0
