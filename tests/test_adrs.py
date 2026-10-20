import re
from pathlib import Path

ADR = Path(__file__).resolve().parent.parent / "docs" / "adr"
NAME = re.compile(r"^\d{4}-[a-z0-9-]+\.md$")
REQUIRED = ("## Status", "## Context", "## Decision", "## Consequences")


def test_adrs_numbered_and_structured():
    adrs = sorted(p for p in ADR.glob("*.md") if NAME.match(p.name))
    assert len(adrs) >= 7
    numbers = [int(p.name[:4]) for p in adrs]
    assert numbers == list(range(1, len(adrs) + 1))
    for path in adrs:
        text = path.read_text(encoding="utf-8")
        for heading in REQUIRED:
            assert heading in text, f"{path.name}: {heading}"


def test_index_lists_every_adr():
    index = (ADR / "README.md").read_text(encoding="utf-8")
    for path in ADR.glob("*.md"):
        if NAME.match(path.name):
            assert path.name in index
