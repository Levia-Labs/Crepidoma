"""Print only the failing test names, file:line lines and error lines of a PR or run.

Usage: ci_failures.py <pr-number|run-id>
A value that resolves as a PR uses its latest failed run; otherwise it is a run id.
Output is deduplicated and capped at 40 lines.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys

CAP = 40
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
STAMP = re.compile(r"^\d{4}-\d\d-\d\dT[\d:.]+Z\s*")
# Log lines are "job<TAB>step<TAB>text"; keep the text only.
WANTED = re.compile(
    r"(^FAILED\b|^---\s*FAIL\b|^FAIL\b|\b[\w./\-]+\.\w{1,5}:\d+(:\d+)?\b|\berror\b|^E\s{2,}|\bpanic:)",
    re.IGNORECASE,
)


def gh(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["gh", *args], capture_output=True, text=True, encoding="utf-8", errors="replace"
    )


def failed_run_for_pr(pr: str) -> str | None:
    view = gh(["pr", "view", pr, "--json", "headRefName"])
    if view.returncode != 0:
        return None
    branch = json.loads(view.stdout)["headRefName"]
    runs = gh(
        [
            "run",
            "list",
            "--branch",
            branch,
            "--status",
            "failure",
            "--limit",
            "1",
            "--json",
            "databaseId",
        ]
    )
    if runs.returncode != 0:
        return None
    items = json.loads(runs.stdout or "[]")
    # "" marks a PR with no failed run, distinct from None (not a PR: treat as run id).
    return str(items[0]["databaseId"]) if items else ""


def filter_log(text: str, cap: int = CAP) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in text.splitlines():
        line = STAMP.sub("", ANSI.sub("", raw.split("\t")[-1])).strip()
        if not line or line in seen or not WANTED.search(line):
            continue
        seen.add(line)
        out.append(line)
        if len(out) >= cap:
            break
    return out


def main(argv: list[str]) -> int:
    if len(argv) != 1 or not argv[0].isdigit():
        print("usage: ci_failures.py <pr-number|run-id>", file=sys.stderr)
        return 2
    found = failed_run_for_pr(argv[0])
    if found == "":
        print(f"no failed run for PR {argv[0]}")
        return 0
    run_id = found or argv[0]
    log = gh(["run", "view", run_id, "--log-failed"])
    if log.returncode != 0:
        print(f"no failed run log for {argv[0]}: {log.stderr.strip()}", file=sys.stderr)
        return 3
    lines = filter_log(log.stdout)
    print(f"run {run_id}")
    print("\n".join(lines) if lines else "no failing lines found")
    return 1 if lines else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
