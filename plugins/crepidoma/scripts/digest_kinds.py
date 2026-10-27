"""Kind-aware digest bodies: Markdown headings, code definitions, log failures, head and tail.

Used by digest.py when the caller passes neither --grep nor --tail. Standard library only.
"""

import re
from collections.abc import Callable

LOG_RX = re.compile(r"FAIL|ERROR|panic|Traceback")
HEADING_RX = re.compile(r"^#{1,6}\s+\S")
DEF_RX = re.compile(
    r"^(?:(?:async\s+)?def|class|func|fn|pub\s+(?:async\s+)?fn|function|export\s+(?:default\s+)?"
    r"(?:async\s+)?(?:function|class|const)|type|struct|interface|impl)\b"
)
CODE_EXT = (".py", ".go", ".rs", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".java", ".c",
            ".h", ".cpp", ".cs", ".sh", ".rb", ".kt", ".swift")  # fmt: skip
LIMIT = 18  # 20 lines minus the header
HEAD_TAIL = 5


def kind_of(name: str, lines: list[str]) -> str:
    low = name.lower()
    if low.endswith((".md", ".markdown")):
        return "markdown"
    if low.endswith(CODE_EXT):
        return "code"
    if low.endswith((".log", ".out", ".output")) or any(LOG_RX.search(x) for x in lines):
        return "log"
    return "text"


def pick(lines: list[str], test: Callable[[str], bool]) -> list[str]:
    found = [f"{n}: {line.strip()}" for n, line in enumerate(lines, 1) if test(line)]
    if len(found) > LIMIT:
        found = [*found[: LIMIT - 1], f"... {len(found) - LIMIT + 1} more"]
    return found


def head_tail(lines: list[str]) -> list[str]:
    if len(lines) <= 2 * HEAD_TAIL:
        return list(lines)
    return [*lines[:HEAD_TAIL], "...", *lines[-HEAD_TAIL:]]


def fenced_free(lines: list[str]) -> list[str]:
    """Markdown headings outside code fences, with line numbers."""
    in_fence = False
    keep = []
    for n, line in enumerate(lines, 1):
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
        elif not in_fence and HEADING_RX.match(line):
            keep.append(f"{n}: {line.strip()}")
    return keep


def body(name: str, lines: list[str]) -> list[str]:
    kind = kind_of(name, lines)
    found: list[str] = []
    if kind == "markdown":
        found = fenced_free(lines)[:LIMIT]
    elif kind == "code":
        found = pick(lines, lambda line: bool(DEF_RX.match(line)))
    elif kind == "log":
        found = pick(lines, lambda line: bool(LOG_RX.search(line)))
    return found or head_tail(lines)
