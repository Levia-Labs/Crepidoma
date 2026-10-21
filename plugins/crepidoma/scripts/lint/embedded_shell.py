#!/usr/bin/env python3
"""shellcheck the shell that lives inside the Taskfiles.

Much of a pillar's logic is shell embedded in YAML - a `- |` block under `cmds:`. shellcheck
lints *files*, and a Taskfile is not a shell file, so none of that shell is covered by
`task lint:shell:check`. This extracts each block to a temporary script and runs shellcheck
over it.

Two reasons this reports rather than gates:

  * go-task templating is not shell. `{{.HOME}}/project` and `{{if .DRY}}--dry-run{{end}}`
    are expanded by the task runner before a shell ever sees them. They are replaced here
    with a placeholder token so the surrounding command still parses, which means the line
    shellcheck examines is not exactly the line that will run.
  * go-task executes each block through its own interpreter (mvdan.cc/sh), which accepts
    much bash syntax. Blocks are checked as POSIX sh because that is the convention, so a
    bash construct is reported even though go-task would run it.

So a finding here is worth reading and is not worth failing a build over. `task lint:check`
does not call this; `task lint:embedded` does.

Usage:
  python3 plugins/crepidoma/scripts/lint/embedded_shell.py            # findings, per task
  python3 plugins/crepidoma/scripts/lint/embedded_shell.py --severity error
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(
    subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
)

# Vendored plugins are upstream's files, kept verbatim.
SKIP = (".claude/marketplace/",)

# A `- |` or `- >` block opens a scalar; everything indented further than the dash belongs
# to it. `-` may carry a chomping or indentation indicator (`|-`, `|2`).
BLOCK = re.compile(r"^(?P<indent>\s*)-\s(?P<style>[|>][-+0-9]*)\s*$")
TASK_NAME = re.compile(r"^  (?P<name>[A-Za-z_][\w:.-]*):\s*$")

# go-task templating, replaced with a token that is a valid shell word so the rest of the
# line still parses. `TASKVAR` rather than a quoted string: a bare word works in both a
# command position and an argument position, which is where these appear.
TEMPLATE = re.compile(r"\{\{.*?\}\}")


def taskfiles() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "*.yml", "*.yaml"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [
        ROOT / line for line in out.splitlines() if not any(line.startswith(skip) for skip in SKIP)
    ]


def blocks(path: Path) -> list[tuple[str, int, str]]:
    """Every embedded shell block in one Taskfile, as (task name, first line number, body)."""
    lines = path.read_text(encoding="utf-8").splitlines()
    found: list[tuple[str, int, str]] = []
    task = "<file>"
    index = 0

    while index < len(lines):
        line = lines[index]

        named = TASK_NAME.match(line)
        if named:
            task = named.group("name")

        opener = BLOCK.match(line)
        if not opener:
            index += 1
            continue

        # The body is everything indented deeper than the dash that opened it. A blank line
        # inside a block does not end it, so blanks are carried and only trailing ones are
        # dropped.
        dash_indent = len(opener.group("indent"))
        start = index + 1
        body: list[str] = []
        index = start
        while index < len(lines):
            candidate = lines[index]
            if candidate.strip() and (len(candidate) - len(candidate.lstrip())) <= dash_indent:
                break
            body.append(candidate)
            index += 1

        while body and not body[-1].strip():
            body.pop()
        if body:
            # Strip the block's own indentation, taken from its first line, so shellcheck
            # sees a script rather than one deeply indented heredoc.
            margin = len(body[0]) - len(body[0].lstrip())
            found.append((task, start + 1, "\n".join(row[margin:] for row in body)))

    return found


def check(body: str, severity: str) -> str:
    """shellcheck one block. Returns its report, or an empty string when clean."""
    script = "#!/bin/sh\n" + TEMPLATE.sub("TASKVAR", body) + "\n"
    with tempfile.TemporaryDirectory() as directory:
        target = Path(directory) / "block.sh"
        target.write_text(script, encoding="utf-8")
        done = subprocess.run(
            ["shellcheck", "--shell=sh", f"--severity={severity}", "--format=gcc", str(target)],
            capture_output=True,
            text=True,
            check=False,
        )
    # --format=gcc prints the temporary path, which means nothing to the reader. The caller
    # knows the Taskfile and line, so the path is stripped here.
    return "\n".join(
        line.split(":", 1)[1] if line.startswith(str(target)) else line
        for line in done.stdout.splitlines()
        if line.strip()
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--severity",
        default="warning",
        choices=("error", "warning", "info", "style"),
        help="lowest severity to report (default: warning)",
    )
    args = parser.parse_args()

    if not shutil.which("shellcheck"):
        print("shellcheck is not on PATH. Install it:  task lint:setup")
        return 0

    total = 0
    for path in taskfiles():
        relative = path.relative_to(ROOT).as_posix()
        for task, line, body in blocks(path):
            report = check(body, args.severity)
            if not report:
                continue
            total += 1
            print(f"\n{relative}:{line}  (task {task})")
            for row in report.splitlines():
                print(f"    {row}")

    print(f"\n{total} embedded block(s) with findings at severity {args.severity} or above.")
    print("Advisory only - go-task runs these through its own interpreter, and the")
    print("{{...}} templating was substituted before the check. Nothing here fails a build.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
