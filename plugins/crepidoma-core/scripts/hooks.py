#!/usr/bin/env python3
"""Claude Code hooks: quality gates at the end of a turn and the agent dispatch policy.

One CLI, one subcommand per hook event; each reads the hook's JSON payload on stdin.

  post-tool-use    after Edit/Write/MultiEdit - marks a gate dirty when the edited file is in
                   its scope
  pre-tool-use     before Agent/Task - refuses a catch-all agent type, a model other than
                   sonnet or haiku, a seventh concurrent agent, or any agent while a usage
                   window is at the ceiling
  pre-bash         before Bash, subagents only - refuses a command that discards or sweeps up
                   working-tree changes other agents made
  subagent-start   a dispatched agent began - its reservation becomes a running lane
  subagent-stop    an agent finished - its lane is freed
  stop             end of a turn - runs the dirty gates' tasks, blocks on failure

Keeping raw file content out of the main thread is raw_read_guard.py's job, not this file's.

Paths are computed from the project directory (CLAUDE_PROJECT_DIR, else the working
directory). Markers, the lane ledger and the usage cache live under .git, never committed.

Contract: the exit code is always 0. A refusal is a `permissionDecision: deny` object and a
Stop block a `decision: block` object, both JSON on stdout. Malformed or empty stdin and any
internal error exit 0 with no output: the hooks fail open. Standard library only.
"""

import argparse
import contextlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import NamedTuple

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd())
PLUGIN_AGENTS = Path(__file__).resolve().parent.parent / "agents"


class Gate(NamedTuple):
    marker: Path
    # A path fragment the edited file must contain; "" accepts any path.
    watched: str
    suffixes: tuple[str, ...]
    tasks: tuple[str, ...]
    # Lines that name a finding, so the block reason stays short.
    hints: tuple[str, ...]
    skip: tuple[str, ...]


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
GATES = (Gate(ROOT / ".git" / "claude-dirty", "", WATCHED_SUFFIXES, ("validate",), (), SKIP),)

PROGRESS = re.compile(r"^[.s]+\s+\[\s*\d+%\]$")
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
)

CEILING = 95.0
USAGE_CACHE = ROOT / ".git" / "claude-usage.json"
# The usage endpoint answers 429 to a tight poll. One reading serves every check inside this.
CACHE_SECONDS = 60
BUDGET_SCRIPTS = ("tasks/claude/budget.py", "Tasks/claude/budget.py")
BUDGET_TIMEOUT = 30

AGENT_TOOLS = ("Agent", "Task")
# No subagent_type means general-purpose. These read freely and relay what they read.
CATCH_ALL = frozenset({"", "general-purpose", "claude", "fork", "Explore", "Plan"})
MODELS = frozenset({"sonnet", "haiku"})
MAX_AGENTS = 6
PENDING_SECONDS = 120
# A lane that crashed never says finished. Past this age it stops holding a slot.
RUNNING_SECONDS = 4 * 3600
LEDGER = ROOT / ".git" / "claude-lanes.json"
LOCK_TRIES = 50
LOCK_STALE_SECONDS = 10

GIT_REASON = (
    "Refused: `{cmd}` discards or sweeps up working-tree changes. Other agents share this "
    "checkout. To undo your own edit, re-edit the file; never discard changes you did not "
    "make. Stage and commit only your own paths: `git add <paths>` and "
    "`git commit -- <paths>`, never `git add -u/-A/.` or `git commit -a`."
)
# One table. Each row: (name, regex over "<subcommand> <args>").
GIT_DENY = (
    ("checkout", r"^checkout\b"),
    ("switch", r"^switch\b"),
    ("restore", r"^restore\b(?!.*(?:--staged\b|\s-[a-zA-Z]*S))"),
    ("restore-worktree", r"^restore\b.*(?:--worktree\b|\s-[a-zA-Z]*W)"),
    ("reset-hard", r"^reset\b.*--(?:hard|merge)\b"),
    ("clean", r"^clean\b"),
    ("stash", r"^stash\b"),
    ("add-all", r"^add\b.*\s(?:-u|--update|-A|--all|\.)(?:\s|$)"),
    ("commit-all", r"^commit\b.*\s(?:-[a-zA-Z]*a[a-zA-Z]*|--all)(?:\s|$)"),
)
GIT_COMPILED = tuple((name, re.compile(rx)) for name, rx in GIT_DENY)
WRAPPERS = {"rtk", "env", "sudo", "command", "time", "exec", "nohup", "nice"}
SHELLS = {"sh", "bash", "zsh", "dash"}
SEPARATORS = re.compile(r"&&|\|\||;|\||\n|&(?!>)")
GLOBAL_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}


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


# ---- Gates -----------------------------------------------------------------------------


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
    if not path:
        return 0
    for gate in GATES:
        if in_scope(path, gate):
            gate.marker.parent.mkdir(parents=True, exist_ok=True)
            gate.marker.touch()
    return 0


def run(*command: str) -> subprocess.CompletedProcess:
    # shutil.which resolves PATHEXT on Windows, so no shell is needed to find `task`.
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
    if event.get("stop_hook_active"):
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


# ---- Usage allowance -------------------------------------------------------------------


def budget_script() -> Path | None:
    return next((ROOT / name for name in BUDGET_SCRIPTS if (ROOT / name).is_file()), None)


def usage_reading() -> dict:
    """The allowance, from a cached reading where one is fresh enough to reuse.

    Unknown answers an empty dict: not knowing the allowance never blocks work.
    """
    with contextlib.suppress(OSError, ValueError, TypeError, AttributeError):
        cached = json.loads(USAGE_CACHE.read_text(encoding="utf-8"))
        if time.time() - float(cached.get("read_at", 0)) < CACHE_SECONDS:
            return cached.get("reading", {})

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


# ---- Agent dispatch --------------------------------------------------------------------


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


def agent_refusal(arguments: dict) -> str | None:
    kind = str(arguments.get("subagent_type") or "").strip()
    if kind in CATCH_ALL:
        return (
            f"Agent type '{kind or 'general-purpose'}' is a generic catch-all and is refused: "
            "it reads files and relays their content. Dispatch a named single-job agent from "
            ".claude/agents/ or a plugin that calls tools and returns a receipt; if none "
            "fits, write one first."
        )
    model = str(arguments.get("model") or defined_model(kind)).strip()
    if model not in MODELS:
        return (
            f"Agent '{kind}' would run on '{model or 'the orchestrator model'}'. Pass model "
            "'sonnet' (work) or 'haiku' (indexing), or declare one in the agent definition."
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


# ---- Git guard -------------------------------------------------------------------------


def is_tracked(path: str, cwd: Path) -> bool:
    """True when git tracks `path` (a pathspec, so globs and directories work)."""
    try:
        done = subprocess.run(
            ["git", "-C", str(cwd), "ls-files", "--", path],
            capture_output=True,
            text=True,
            timeout=15,
            shell=False,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return bool(done.stdout.strip())


def strip_prefix(tokens: list[str]) -> list[str]:
    """Drop `VAR=x` assignments and wrapper commands ahead of the real command."""
    i = 0
    while i < len(tokens) and (
        re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[i]) or Path(tokens[i]).name in WRAPPERS
    ):
        i += 1
    return tokens[i:]


def git_args(tokens: list[str]) -> list[str]:
    """Tokens after `git` with global options removed: [subcommand, args...]."""
    i = 1
    while i < len(tokens) and tokens[i].startswith("-"):
        name = tokens[i].split("=", 1)[0]
        i += 2 if name in GLOBAL_WITH_VALUE and "=" not in tokens[i] else 1
    return tokens[i:]


def under(path: Path, parents: tuple[Path, ...]) -> bool:
    return any(path.is_relative_to(parent.resolve()) for parent in parents)


def rm_refusal(tokens: list[str], cwd: Path, tracked: Callable[[str, Path], bool]) -> str:
    paths, literal = [], False
    for token in tokens[1:]:
        if literal or not token.startswith("-"):
            paths.append(token)
        elif token == "--":  # noqa: S105 - argv separator, not a password
            literal = True
    root = ROOT.resolve()
    safe = (ROOT / "build", Path(tempfile.gettempdir()))
    for raw in paths:
        full = Path(raw).resolve() if Path(raw).is_absolute() else (cwd / raw).resolve()
        if under(full, safe) or not full.is_relative_to(root):
            continue
        if tracked(full.relative_to(root).as_posix(), root):
            return "rm " + raw
    return ""


def segment_refusal(tokens: list[str], cwd: Path, tracked: Callable[[str, Path], bool]) -> str:
    tokens = strip_prefix(tokens)
    if not tokens:
        return ""
    head = Path(tokens[0]).name.removesuffix(".exe")
    if head in SHELLS and "-c" in tokens:
        return inner_refusal(" ".join(tokens[tokens.index("-c") + 1 :]), cwd, tracked)
    if head == "rm":
        return rm_refusal(tokens, cwd, tracked)
    if head != "git":
        return ""
    text = " ".join(git_args(tokens))
    if any(rx.search(text) for _name, rx in GIT_COMPILED):
        return "git " + text
    return ""


def inner_refusal(command: str, cwd: Path, tracked: Callable[[str, Path], bool]) -> str:
    for part in SEPARATORS.split(command):
        try:
            tokens = shlex.split(part, posix=True)
        except ValueError:
            continue
        found = segment_refusal(tokens, cwd, tracked)
        if found:
            return found
    return ""


def git_refusal(
    command: str,
    cwd: str | Path | None = None,
    tracked: Callable[[str, Path], bool] | None = None,
) -> str:
    """The refusal text for `command`, or "" when it may run. Unparseable commands pass."""
    found = inner_refusal(command, Path(cwd) if cwd else ROOT, tracked or is_tracked)
    return GIT_REASON.format(cmd=found) if found else ""


def pre_bash(event: dict) -> int:
    # The main thread is not affected: only a subagent's input carries agent_id.
    if event.get("tool_name") != "Bash" or not event.get("agent_id"):
        return 0
    reason = git_refusal(str(tool_input(event).get("command") or ""), cwd=event.get("cwd"))
    return deny(reason) if reason else 0


# ---- CLI -------------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hooks.py", description="Claude Code hooks; the event payload is JSON on stdin."
    )
    events = parser.add_subparsers(dest="event", required=True, metavar="EVENT")
    events.add_parser("post-tool-use", help="mark a gate dirty after an edit in its scope")
    events.add_parser("pre-tool-use", help="refuse a forbidden, excess or over-budget agent")
    events.add_parser("pre-bash", help="refuse a subagent's working-tree discard")
    events.add_parser("subagent-start", help="record a running lane")
    events.add_parser("subagent-stop", help="free a lane")
    gate = events.add_parser("stop", help="run the dirty gates; block on failure")
    gate.add_argument(
        "--task",
        action="append",
        default=[],
        help="task to run for every dirty gate instead of its own (repeatable)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as error:
        return error.code if isinstance(error.code, int) else 2

    event = payload()
    if not event:
        return 0

    handlers = {
        "post-tool-use": post_tool_use,
        "pre-tool-use": pre_tool_use,
        "pre-bash": pre_bash,
        "subagent-start": subagent_start,
        "subagent-stop": subagent_stop,
        "stop": stop,
    }
    try:
        if args.event == "stop" and args.task:
            return stop(event, tuple(args.task))
        return handlers[args.event](event)
    except Exception:
        return 0


if __name__ == "__main__":
    sys.exit(main())
