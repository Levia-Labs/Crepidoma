"""Bash guards for every caller: stdin-reading interpreters, kill-by-name, raw commit.

These patterns hang a background shell, end other agents' work or skip the commit task,
so they apply to the main thread and to subagents alike. Each refusal names the
alternative. The subagent-only git guard stays in hooks_bash.
"""

import re
import shlex

# hooks_bash imports this module lazily (inside pre_bash), so this import is not circular.
from hooks_bash import SHELLS, git_args, split_unquoted, strip_prefix

REASONS = {
    "stdin": (
        "Refused: `{cmd}` reads its script from stdin and hangs when run in the background. "
        "Write the script to a file and run it (`uv run python script.py`), or use a task."
    ),
    "kill": (
        "Refused: `{cmd}` kills processes by name or image and can end other agents' work. "
        "Kill only your own PID: `kill <pid>` or `taskkill /PID <pid>`."
    ),
    "commit": (
        "Refused: `{cmd}` is a raw commit. Commit through "
        '`task git:commit -- "<message>"` (main thread only; subagents never commit).'
    ),
}
INTERPRETER = re.compile(r"^(python(\d+(\.\d+)*)?|py|node)$")
HEREDOC = re.compile(r"<<-?\s*['\"]?[A-Za-z_]")
# Options after which the script text or module is inline, never read from stdin.
INLINE = re.compile(r"^-(?:[a-zA-Z]*[cmep])$|^--(?:eval|print|command)$")
POWERSHELL = {"powershell", "pwsh", "cmd"}


def head_name(token: str) -> str:
    return re.split(r"[\\/]", token)[-1].lower().removesuffix(".exe")


def interpreter_index(tokens: list[str]) -> int | None:
    """Index of the interpreter token, directly or after `uv run [options]`."""
    head = head_name(tokens[0])
    if INTERPRETER.match(head):
        return 0
    if head == "uv" and "run" in tokens[1:]:
        for i in range(tokens.index("run") + 1, len(tokens)):
            if INTERPRETER.match(head_name(tokens[i])):
                return i
    return None


def reads_stdin(args: list[str], segment: str) -> bool:
    if HEREDOC.search(segment) or not args:
        return True
    for arg in args:
        if arg == "-":
            return True
        if INLINE.match(arg) or not arg.startswith("-"):
            return False  # inline code, or a script path whose later "-" is its own argument
    return False


def segment_kind(tokens: list[str], segment: str) -> tuple[str, str]:
    """(kind, shown command) for a refused segment, else ("", "")."""
    tokens = strip_prefix(tokens)
    if not tokens:
        return "", ""
    head = head_name(tokens[0])
    lowered = [t.lower() for t in tokens[1:]]
    if head == "taskkill" and any(t.split(":")[0] in ("/im", "-im") for t in lowered):
        return "kill", "taskkill /IM"
    if head in ("pkill", "killall"):
        return "kill", head
    if head in ("stop-process", "spps") and not any(t.startswith("-id") for t in lowered):
        return "kill", "Stop-Process by name"
    if head == "git" and git_args(tokens)[:1] == ["commit"]:
        return "commit", "git commit"
    index = interpreter_index(tokens)
    if index is not None and reads_stdin(tokens[index + 1 :], segment):
        return "stdin", " ".join(tokens[: index + 1]) + " -"
    return "", ""


def inner_text(tokens: list[str]) -> str:
    """The script text handed to `sh -c` or `powershell -Command`, or ""."""
    tokens = strip_prefix(tokens)
    if not tokens:
        return ""
    head = head_name(tokens[0])
    for i, token in enumerate(tokens[1:], 1):
        low = token.lower()
        if head in SHELLS and re.fullmatch(r"-[a-z]*c[a-z]*", low):
            return " ".join(tokens[i + 1 :])
        if head in POWERSHELL and low in ("-command", "-c", "/c", "/k"):
            return " ".join(tokens[i + 1 :])
    return ""


def bash_refusal(command: str, depth: int = 0) -> str:
    """Refusal text for `command`, or "" when it may run. Unparseable segments pass."""
    for part in split_unquoted(command):
        try:
            tokens = shlex.split(part, posix=True)
        except ValueError:
            continue
        kind, shown = segment_kind(tokens, part)
        if kind:
            return REASONS[kind].format(cmd=shown)
        inner = inner_text(tokens) if depth < 3 else ""
        found = bash_refusal(inner, depth + 1) if inner else ""
        if found:
            return found
    return ""
