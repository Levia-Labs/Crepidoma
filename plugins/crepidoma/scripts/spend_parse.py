"""Transcript parsing for spend.py (stdlib only): tool calls, result sizes, usage per run.

Not a command; `spend.py` imports it. `scan(path, run)` fills a `spend.Run` from one JSONL file.
"""

import json
import re
import shlex
from datetime import datetime
from pathlib import Path

READ_COMMANDS = {"cat", "head", "tail", "sed"}
SEGMENT = re.compile(r"\r?\n|&&|\|\||[|;&]")
SUMMARY_CHARS = 60


def blocks(entry: dict) -> list[dict]:
    message = entry.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    return [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []


def result_bytes(content: object) -> int:
    if isinstance(content, str):
        return len(content.encode("utf-8", "replace"))
    if isinstance(content, list):
        return sum(
            len(str(b.get("text", "")).encode("utf-8", "replace"))
            for b in content
            if isinstance(b, dict)
        )
    return 0


def bash_read_files(command: str) -> list[str]:
    """Files named by a cat/head/tail/sed invocation (first such command in the string)."""
    for segment in SEGMENT.split(command.replace("2>&1", "")):
        files = segment_read_files(segment)
        if files is not None:
            return files
    return []


def segment_read_files(segment: str) -> list[str] | None:
    """Files of one simple command, or None when it is not a read command."""
    try:
        tokens = shlex.split(segment, posix=True)
    except ValueError:
        tokens = segment.split()
    if not tokens or Path(tokens[0]).name not in READ_COMMANDS:
        return None
    skip_script = Path(tokens[0]).name == "sed"
    files: list[str] = []
    for arg in tokens[1:]:
        if arg in {">", ">>", "2>&1"}:
            break
        if arg.startswith("-") or arg.isdigit():
            continue
        if skip_script:
            skip_script = False
            continue
        files.append(arg)
    return files


def input_summary(params: dict) -> str:
    """First 60 chars of the command or path (or pattern/description) of a tool call."""
    for key in ("command", "file_path", "path", "pattern", "url", "query", "description"):
        if params.get(key):
            return " ".join(str(params[key]).split())[:SUMMARY_CHARS]
    return " ".join(json.dumps(params, sort_keys=True).split())[:SUMMARY_CHARS] if params else ""


def scan(path: Path, run) -> None:
    seen: set[str] = set()
    pending: dict[str, tuple[str, list[str], str]] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if not isinstance(entry, dict):
            continue
        if not run.date and isinstance(entry.get("timestamp"), str):
            run.date = entry["timestamp"][:10]
        message = entry.get("message")
        if isinstance(message, dict) and isinstance(message.get("usage"), dict):
            # One API response is split across entries sharing id and usage: count once.
            key = str(message.get("id") or entry.get("uuid") or len(seen))
            if key not in seen:
                seen.add(key)
                run.add_usage(str(message.get("model") or "?"), message["usage"])
        for block in blocks(entry):
            if block.get("type") == "tool_use":
                tool = str(block.get("name"))
                params = block.get("input") if isinstance(block.get("input"), dict) else {}
                files: list[str] = []
                if tool == "Read" and params.get("file_path"):
                    files = [str(params["file_path"])]
                elif tool == "Bash":
                    files = bash_read_files(str(params.get("command", "")))
                files = [f.replace("\\", "/") for f in files]
                pending[str(block.get("id"))] = (tool, files, input_summary(params))
                run.tool_calls[tool] += 1
            elif block.get("type") == "tool_result":
                tool, files, summary = pending.get(str(block.get("tool_use_id")), ("?", [], ""))
                size = result_bytes(block.get("content"))
                run.tool_bytes[tool] += size
                run.calls.append((tool, summary, size))
                for file in files:
                    run.read_bytes[file] += size // len(files)
    if not run.date:
        run.date = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")
