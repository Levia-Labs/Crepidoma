"""SessionStart hook: emit Crepidoma directives as additional context.

Reads directives/*.md in name order and prints the SessionStart JSON contract.
Never blocks a session: failures become a one-line notice in the context.
"""

from __future__ import annotations

import json
from pathlib import Path

DIRECTIVES = Path(__file__).resolve().parent.parent / "directives"
LIMIT = 10_000
TRUNCATED = "\n[crepidoma: directives truncated at 10000 characters]"


def build(directory: Path) -> str:
    if not directory.is_dir():
        raise FileNotFoundError(directory)
    parts = [path.read_text(encoding="utf-8").strip() for path in sorted(directory.glob("*.md"))]
    return "\n\n".join(parts)


def payload(text: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}


def main() -> int:
    try:
        text = build(DIRECTIVES)
    except (OSError, ValueError) as error:  # ValueError covers undecodable files
        text = f"Crepidoma directives unavailable: {error}"
    if len(text) > LIMIT:
        text = text[: LIMIT - len(TRUNCATED)] + TRUNCATED
    print(json.dumps(payload(text)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
