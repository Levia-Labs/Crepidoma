"""SessionStart and SubagentStart hook: emit Crepidoma directives as additional context.

Reads directives/*.md in name order and prints the SessionStart JSON contract.
Never blocks a session: failures become a one-line notice in the context.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

DIRECTIVES = Path(__file__).resolve().parent.parent / "directives"
LIMIT = 10_000
TRUNCATED = "\n[crepidoma: directives truncated at 10000 characters]"


def build(directory: Path) -> str:
    if not directory.is_dir():
        raise FileNotFoundError(directory)
    paths = [p for p in sorted(directory.glob("*.md")) if p.name != "README.md"]
    parts = [path.read_text(encoding="utf-8").strip() for path in paths]
    return "\n\n".join(parts)


def payload(text: str, event: str = "SessionStart") -> dict:
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--event", choices=["SessionStart", "SubagentStart"], default="SessionStart"
    )
    event = parser.parse_args(argv).event
    # Main thread gets the full set; subagents get the compact harness in directives/subagent/.
    directory = DIRECTIVES / "subagent" if event == "SubagentStart" else DIRECTIVES
    try:
        text = build(directory)
    except (OSError, ValueError) as error:  # ValueError covers undecodable files
        text = f"Crepidoma directives unavailable: {error}"
    if len(text) > LIMIT:
        text = text[: LIMIT - len(TRUNCATED)] + TRUNCATED
    print(json.dumps(payload(text, event)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
