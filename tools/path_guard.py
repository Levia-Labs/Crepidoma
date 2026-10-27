"""Path guard shared by tools that write files named on the command line.

A path is accepted only when it resolves (symlinks followed) inside the git toplevel of the
working directory. Config and hook files are refused on top of that so a tool call cannot rewrite
the rules that police it.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

DENIED_DIRS = {".git", ".claude"}
DENIED_NAMES = {"settings.json", "settings.local.json", "hooks.json", ".pre-commit-config.yaml"}


def toplevel() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, encoding="utf-8"
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise ValueError("not inside a git work tree")
    return Path(result.stdout.strip()).resolve()


def checked(path: Path, *, protect_config: bool = True) -> Path:
    """Return the resolved path; raise ValueError when it escapes the repo or is protected."""
    root = toplevel()
    resolved = path.resolve()
    try:
        parts = resolved.relative_to(root).parts
    except ValueError:
        raise ValueError(f"{path} is outside the repository {root}") from None
    if any(part.lower() in DENIED_DIRS for part in parts):
        raise ValueError(f"{path} is under a protected folder (.git or .claude)")
    if protect_config and parts and parts[-1].lower() in DENIED_NAMES:
        raise ValueError(f"{path} is a protected config file")
    return resolved
