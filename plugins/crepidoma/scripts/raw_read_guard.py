#!/usr/bin/env python3
"""PreToolUse hook: keep raw file content out of the main Claude thread (stdlib only).

JSON on stdin, contract as scripts/hooks.py: a refusal is a
`permissionDecision: deny` object on stdout, exit 0; allowing prints nothing.

It acts only in the main thread. A subagent's input carries `agent_id`
(https://code.claude.com/docs/en/hooks#common-input-fields) and is allowed
everything. In the main thread it denies a Read with no `limit` or one above
20, and a Bash command that reads file content raw (cat, head/tail above 20
lines or 1024 bytes, a wide sed range, less, more, Get-Content, type, any
`*/tasks/*.output`), unless it goes through digest, wc or grep -c.

It fails open: malformed input, an unknown tool or any internal error allows.

Copied to ~/.claude/bin by `task claude:guard:install`; plain `python`, no
imports outside the standard library.
"""

import json
import re
import sys

# ---- Patterns and limits: adjust here. ------------------------------------
MAX_LINES = 20
MAX_BYTES = 1024
DEFAULT_TAIL_HEAD_LINES = 10  # head/tail with no -n: allowed
PAGERS = {"less", "more"}
WINDOWS_READERS = {"get-content", "gc", "type"}
PS_LIMIT_FLAGS = r"-(?:totalcount|head|first|tail|last)"
SED_RANGE = re.compile(r"""^['"]?(\d+),(\d+|\$)p['"]?$""")
TASK_OUTPUT = re.compile(r"/tasks/[^\s'\"]*\.output", re.IGNORECASE)
SINKS = (
    re.compile(r"(^|[\s/\\])digest(\.py)?\b"),
    re.compile(r"^(wc)(\s|$)"),
    re.compile(r"^grep\s+(-[a-zA-Z]*c[a-zA-Z]*|--count)(\s|$)"),
)
WRAPPERS = {"rtk", "sudo", "env", "command", "builtin", "time"}
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")
# ----------------------------------------------------------------------------

DIGEST = "digest"


def reason(what: str) -> str:
    return (
        f"Raw read refused in the main thread ({what}). Qualify it first: "
        f"`{DIGEST} <file>` (or `<cmd> | {DIGEST}`), or hand the read to a "
        "haiku agent when prose must be summarised."
    )


def split_unquoted(command: str, seps: str) -> list[str]:
    """Split on any char of `seps` outside quotes; `&&`, `||`, `;` and newline all split."""
    parts, buf, quote = [], [], ""
    prev = ""
    for pos, ch in enumerate(command):
        nxt = command[pos + 1 : pos + 2]
        redirect_amp = ch == "&" and (prev == ">" or nxt == ">")
        prev = ch
        if redirect_amp:
            buf.append(ch)
        elif quote:
            buf.append(ch)
            if ch == quote:
                quote = ""
        elif ch in "'\"":
            quote = ch
            buf.append(ch)
        elif ch in seps:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    parts.append("".join(buf))
    return [p.strip() for p in parts if p.strip()]


def tokens(stage: str) -> list[str]:
    return re.findall(r"\"[^\"]*\"|'[^']*'|\S+", stage)


def command_word(toks: list[str]) -> tuple[str, list[str]]:
    i = 0
    while i < len(toks) and (toks[i].lower() in WRAPPERS or re.match(r"^\w+=", toks[i])):
        i += 1
    if i >= len(toks):
        return "", []
    word = toks[i].strip("\"'").replace("\\", "/").rsplit("/", 1)[-1].lower()
    if word.endswith(".exe"):
        word = word[:-4]
    return word, toks[i + 1 :]


def is_sink(stage: str) -> bool:
    return any(p.search(stage.strip()) for p in SINKS)


def count_arg(args: list[str], short: str, long: str) -> int | None:
    """Value of -n/-c style flags (-n 5, -n5, -5, --lines=5), 'bad' as huge for sign prefixes."""
    value = None
    for i, a in enumerate(args):
        raw = None
        m = re.match(rf"^-{short}\s*([+-]?\d+)[a-zA-Z]*$", a) or re.match(
            rf"^--{long}=([+-]?\d+)", a
        )
        if m:
            raw = m.group(1)
        elif a in (f"-{short}", f"--{long}") and i + 1 < len(args):
            raw = args[i + 1]
        elif short == "n" and re.match(r"^-\d+$", a):
            raw = a[1:]
        if raw is not None:
            if not re.match(r"^\d+$", raw):
                return 10**9
            value = int(raw)
    return value


def has_file_arg(args: list[str]) -> bool:
    return any(not a.startswith(("-", ">", "<", "2>", "&>")) for a in args)


def check_stage(word: str, args: list[str], stage: str) -> str | None:
    """A denial reason for one pipeline stage, or None."""
    if word == "cat":
        redirect = any(a.startswith((">", "<", "2>", "&>")) or ">" in a for a in args)
        if redirect and (">" in stage):
            return None
        if has_file_arg(args):
            return "cat of a file"
        return None
    if word in ("head", "tail"):
        lines = count_arg(args, "n", "lines")
        size = count_arg(args, "c", "bytes")
        if lines is not None and lines > MAX_LINES:
            return f"{word} -n {lines}"
        if size is not None and size > MAX_BYTES:
            return f"{word} -c {size}"
        return None
    if word == "sed":
        quiet = any(re.match(r"^-[a-zA-Z]*n[a-zA-Z]*$", a) or a == "--quiet" for a in args)
        if quiet:
            for a in args:
                m = SED_RANGE.match(a)
                if m:
                    end = m.group(2)
                    if end == "$" or int(end) - int(m.group(1)) + 1 > MAX_LINES:
                        return f"sed -n {a}"
        return None
    if word in PAGERS:
        return word
    if word in WINDOWS_READERS and has_file_arg(args):
        m = re.search(rf"{PS_LIMIT_FLAGS}\s+(\d+)", stage, re.IGNORECASE)
        if m and int(m.group(1)) <= MAX_LINES:
            return None
        return word
    return None


def check_bash(command: str) -> str | None:
    sinks = [s for st in split_unquoted(command, ";&\n") for s in split_unquoted(st, "|")]
    if TASK_OUTPUT.search(command.replace("\\", "/")) and not any(map(is_sink, sinks)):
        return "a task .output file"
    for statement in split_unquoted(command, ";&\n"):
        stages = split_unquoted(statement, "|")
        for index, stage in enumerate(stages):
            word, args = command_word(tokens(stage))
            found = check_stage(word, args, stage)
            if found and not any(is_sink(s) for s in stages[index + 1 :]):
                return found
    return None


def decide(data: dict) -> str | None:
    """Denial reason, or None to allow."""
    if data.get("agent_id"):
        return None
    tool, args = data.get("tool_name"), data.get("tool_input") or {}
    if tool == "Read":
        path = str(args.get("file_path", "")).lower()
        if path.endswith(IMAGE_EXT):
            return None
        try:
            limit = int(args["limit"]) if args.get("limit") is not None else None
        except (TypeError, ValueError):
            limit = None
        if limit is None or limit > MAX_LINES:
            return reason(f"Read limit {limit if limit is not None else 'unset'}, max {MAX_LINES}")
    elif tool == "Bash":
        found = check_bash(str(args.get("command", "")))
        if found:
            return reason(found)
    return None


def main() -> int:
    try:
        denial = decide(json.load(sys.stdin))
    except Exception:
        return 0
    if denial:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": denial,
                    }
                }
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
