"""The git guard: refuses a subagent's push, working-tree discard or sweeping stage."""

import re
import shlex
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

from hooks_common import ROOT, deny, tool_input

GIT_REASON = (
    "Refused: `{cmd}` pushes, discards or sweeps up changes. Other agents share this "
    "checkout. To undo your own edit, re-edit the file; never discard changes you did not "
    "make. Stage only your own paths with `git add <paths>`, never `git add -u/-A/--all/.`; "
    "the main thread commits through `task git:commit`."
)
# One table. Each row: (name, regex over "<subcommand> <args>").
GIT_DENY = (
    ("checkout", r"^checkout\b"),
    ("switch", r"^switch\b"),
    ("restore", r"^restore\b(?!.*(?:--staged\b|\s-[a-zA-Z]*S))"),
    ("restore-worktree", r"^restore\b.*(?:--worktree\b|\s-[a-zA-Z]*W)"),
    ("reset-hard", r"^reset\b.*--(?:hard|merge|keep)\b"),
    ("rm", r"^rm\b(?!.*--cached\b)"),
    ("checkout-index", r"^checkout-index\b"),
    ("read-tree-update", r"^read-tree\b.*\s(?:-u|--reset)\b"),
    ("clean", r"^clean\b"),
    ("stash", r"^stash\b"),
    ("add-all", r"^add\b.*\s(?:-u|--update|-A|--all|\.)(?:\s|$)"),
    ("commit-all", r"^commit\b.*\s(?:-[a-zA-Z]*a[a-zA-Z]*|--all)(?:\s|$)"),
    ("push", r"^push\b"),  # main thread only; settings no longer deny it
)
GIT_COMPILED = tuple((name, re.compile(rx)) for name, rx in GIT_DENY)
WRAPPERS = {"rtk", "env", "sudo", "command", "time", "exec", "nohup", "nice"}
SHELLS = {"sh", "bash", "zsh", "dash"}
GLOBAL_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}


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
    if head in SHELLS:
        # Any short-option cluster holding c (-c, -lc, -ec) runs the next word as a script.
        flag = next(
            (i for i, t in enumerate(tokens[1:], 1) if re.fullmatch(r"-[a-zA-Z]*c[a-zA-Z]*", t)),
            None,
        )
        if flag is not None:
            return inner_refusal(" ".join(tokens[flag + 1 :]), cwd, tracked)
    if head == "rm":
        return rm_refusal(tokens, cwd, tracked)
    if head == "task" and "git:commit" in tokens[1:]:
        return "task git:commit (adds, commits and pushes; main thread only)"
    text = " ".join(git_args(tokens)) if head == "git" else ""
    if text and any(rx.search(text) for _name, rx in GIT_COMPILED):
        return "git " + text
    return ""


def split_unquoted(command: str) -> list[str]:
    """Split on ; | & && || and newlines outside quotes and $( ), so quoted text stays whole."""
    parts: list[str] = []
    current: list[str] = []
    quote = ""
    depth = 0
    i = 0
    n = len(command)
    while i < n:
        ch = command[i]
        if quote:
            current.append(ch)
            if ch == "\\" and quote == '"' and i + 1 < n:
                current.append(command[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = ""
            i += 1
            continue
        if ch in "'\"":
            quote = ch
        elif ch == "\\" and i + 1 < n:
            current.append(command[i : i + 2])
            i += 2
            continue
        elif command.startswith("$(", i):
            depth += 1
        elif ch == ")" and depth:
            depth -= 1
        elif depth == 0:
            double = command.startswith(("&&", "||"), i)
            redirect = ch == "&" and (command[i - 1 : i] == ">" or command[i + 1 : i + 2] == ">")
            if double or ch in ";|\n" or (ch == "&" and not redirect):
                parts.append("".join(current))
                current = []
                i += 2 if double else 1
                continue
        current.append(ch)
        i += 1
    parts.append("".join(current))
    return parts


def inner_refusal(command: str, cwd: Path, tracked: Callable[[str, Path], bool]) -> str:
    for part in split_unquoted(command):
        try:
            tokens = shlex.split(part, posix=True)
        except ValueError:
            # Fail closed: a segment that cannot be parsed cannot be cleared.
            return "unparseable command " + part.strip()
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
    if event.get("tool_name") != "Bash":
        return 0
    command = str(tool_input(event).get("command") or "")
    # Imported here: hooks_bash_guards imports this module's helpers.
    from hooks_bash_guards import bash_refusal

    reason = bash_refusal(command)
    if reason:
        return deny(reason)
    # The git guard is subagent-only: only a subagent's input carries agent_id.
    if not event.get("agent_id"):
        return 0
    reason = git_refusal(command, cwd=event.get("cwd"))
    return deny(reason) if reason else 0
