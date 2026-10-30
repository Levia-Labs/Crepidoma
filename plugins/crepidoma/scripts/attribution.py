"""Flag AI attribution (Claude co-author trailers, "Generated with Claude Code") in commit messages.

Modes: `msg FILE` checks one commit message file (commit-msg hook); `range [REV_RANGE]` checks
every commit message in a range. One line per hit; exit 1 on any hit, 0 when clean.
"""

import re
import subprocess  # nosec B404 - fixed git argv, no shell
import sys
from pathlib import Path

PATTERNS = (
    re.compile(r"co-authored-by\s*:[^\n]*(claude|anthropic)", re.IGNORECASE),
    re.compile(r"generated\s+with\s+(\[\s*)?claude\s+code", re.IGNORECASE),
    re.compile(r"noreply@anthropic\.com", re.IGNORECASE),
)
DIRECTIVE = "directive 30-conventions item 15: never add AI attribution"


def hits(text: str) -> list[tuple[int, str]]:
    """(1-based line number, stripped line) for every line carrying AI attribution."""
    return [
        (number, line.strip())
        for number, line in enumerate(text.splitlines(), 1)
        if any(pattern.search(line) for pattern in PATTERNS)
    ]


def has_attribution(text: str) -> bool:
    return bool(hits(text))


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # nosec B603 B607 - fixed git argv, no shell
        ["git", *args], capture_output=True, text=True, encoding="utf-8", check=False
    )


def resolves(rev: str) -> bool:
    return git("rev-parse", "--verify", "--quiet", rev).returncode == 0


def default_range() -> str:
    for candidate in ("origin/main", "@{u}"):
        if resolves(candidate):
            return f"{candidate}..HEAD"
    return "HEAD~1..HEAD" if resolves("HEAD~1") else "HEAD"


def check_msg(path: str) -> int:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    lines = hits(text)
    for number, line in lines:
        print(f"{path}:{number}: {line}")
    if lines:
        print(f"Refused: {DIRECTIVE}.")
    return 1 if lines else 0


def check_range(rev_range: str) -> int:
    log = git("rev-list", rev_range)
    if log.returncode != 0:
        print(f"git rev-list {rev_range} failed: {log.stderr.strip()}", file=sys.stderr)
        return 2
    bad = 0
    for sha in log.stdout.split():
        for _, line in hits(git("show", "-s", "--format=%B", sha).stdout):
            print(f"{sha[:10]}: {line}")
            bad += 1
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) == 2 and args[0] == "msg":
        return check_msg(args[1])
    if args and args[0] == "range" and len(args) <= 2:
        return check_range(args[1] if len(args) == 2 else default_range())
    print("Usage: attribution.py msg FILE | range [REV_RANGE]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
