"""List references to a symbol in tracked source files.

Usage: code_refs.py SYMBOL [PATH]. `git grep -n -w`, at most 40 `file:line: text` lines (text cut
to 120 characters) and a total count. Docs, data and lockfiles are skipped.
"""

from __future__ import annotations

import subprocess
import sys

LIMIT = 40
WIDTH = 120
# Extension pathspecs keep prose, lockfiles and data out of the hit list.
SOURCE = [
    "py",
    "go",
    "rs",
    "ts",
    "tsx",
    "js",
    "jsx",
    "mjs",
    "cjs",
    "java",
    "kt",
    "cs",
    "c",
    "h",
    "cc",
    "cpp",
    "hpp",
    "rb",
    "php",
    "swift",
    "scala",
    "sh",
    "ps1",
    "lua",
    "sql",
]


def pathspecs(path: str | None) -> list[str]:
    base = f"{path.rstrip('/')}/" if path else ""
    return [f"{base}*.{ext}" if base else f"*.{ext}" for ext in SOURCE]


def main(argv: list[str]) -> int:
    if not 1 <= len(argv) <= 2 or not argv[0]:
        print("usage: code_refs.py SYMBOL [PATH]", file=sys.stderr)
        return 2
    command = ["git", "grep", "-n", "-w", "-I", "-e", argv[0], "--"]
    command += pathspecs(argv[1] if len(argv) == 2 else None)
    result = subprocess.run(
        command, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if result.returncode not in (0, 1):
        print(result.stderr.strip(), file=sys.stderr)
        return result.returncode
    hits = result.stdout.splitlines()
    for hit in hits[:LIMIT]:
        place, _, rest = hit.partition(":")
        number, _, text = rest.partition(":")
        print(f"{place}:{number}: {text.strip()[:WIDTH]}")
    print(f"total {len(hits)}" + (f" (showing {LIMIT})" if len(hits) > LIMIT else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
