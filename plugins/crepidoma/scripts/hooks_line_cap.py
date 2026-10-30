"""The 300-line source cap, enforced at edit time: PreToolUse refuses, PostToolUse warns.

Mirrors the long-file ratchet (which files are capped, where the baseline lives, what a
baselined file may do) so an agent never needs a separate headroom check. A file over the
cap is allowed only when `.ratchet/long-files.baseline` lists it and the change does not
grow it past its baseline. Every error fails open.
"""

import json
from pathlib import Path

from hooks_common import ROOT, deny, tool_input

MAX_LINES = 300
WARN_AT = 270
BASELINE = Path(".ratchet") / "long-files.baseline"
EDIT_TOOLS = ("Write", "Edit", "MultiEdit")
# Same exclusions as the ratchet: lockfiles, its own baselines and binary files.
LOCKFILES = frozenset(
    {
        "uv.lock",
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "Cargo.lock",
        "poetry.lock",
        "Gemfile.lock",
        "composer.lock",
        "go.sum",
    }
)


def count(text: str) -> int:
    return text.count("\n") + (1 if text and not text.endswith("\n") else 0)


def key(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def capped(path: Path, root: Path) -> bool:
    return path.name not in LOCKFILES and ".ratchet" not in Path(key(path, root)).parts


def baseline_limit(name: str, root: Path) -> int | None:
    try:
        text = (root / BASELINE).read_text(encoding="utf-8")
    except OSError:
        return None
    for line in text.splitlines():
        entry, _, value = line.rpartition("\t")
        if entry == name and value.strip().isdigit():
            return int(value)
    return None


def read_text(path: Path) -> str | None:
    try:
        data = path.read_bytes()
        if b"\0" in data[:8192]:
            return None
        return data.decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def apply(text: str, edit: dict) -> str | None:
    old, new = edit.get("old_string"), edit.get("new_string")
    if not isinstance(old, str) or not isinstance(new, str) or not old or old not in text:
        return None
    return text.replace(old, new) if edit.get("replace_all") else text.replace(old, new, 1)


def projected(event: dict, path: Path) -> str | None:
    """The file text after the tool runs, or None when it cannot be worked out."""
    data = tool_input(event)
    tool = event.get("tool_name")
    if tool == "Write":
        content = data.get("content")
        return content if isinstance(content, str) else None
    text = read_text(path)
    if text is None:
        return None
    edits = data.get("edits") if tool == "MultiEdit" else [data]
    for edit in edits if isinstance(edits, list) else []:
        text = apply(text, edit) if isinstance(edit, dict) else None
        if text is None:
            return None
    return text


def refusal(event: dict, root: Path | None = None) -> str | None:
    root = root or ROOT
    if event.get("tool_name") not in EDIT_TOOLS:
        return None
    raw = str(tool_input(event).get("file_path") or "")
    if not raw:
        return None
    path = Path(raw) if Path(raw).is_absolute() else root / raw
    if not capped(path, root):
        return None
    text = projected(event, path)
    if text is None or "\0" in text[:8192]:
        return None
    lines = count(text)
    if lines <= MAX_LINES:
        return None
    name = key(path, root)
    limit = baseline_limit(name, root)
    if limit is not None and lines <= limit:
        return None
    return (
        f"{name} would be {lines} lines, over the {MAX_LINES}-line cap"
        + (f" and its baseline of {limit}" if limit is not None else "")
        + ". Split the file into smaller modules instead of growing it."
    )


def warning(event: dict, root: Path | None = None) -> str | None:
    root = root or ROOT
    if event.get("tool_name") not in EDIT_TOOLS:
        return None
    raw = str(tool_input(event).get("file_path") or "")
    if not raw:
        return None
    path = Path(raw) if Path(raw).is_absolute() else root / raw
    if not capped(path, root):
        return None
    text = read_text(path)
    if text is None:
        return None
    lines = count(text)
    return f"{key(path, root)}: {lines}/{MAX_LINES} lines" if lines >= WARN_AT else None


def pre_edit(event: dict) -> int:
    reason = refusal(event, ROOT)
    return deny(reason) if reason else 0


def post_edit(event: dict) -> int:
    note = warning(event, ROOT)
    if note:
        out = {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": note}}
        print(json.dumps(out))
    return 0
