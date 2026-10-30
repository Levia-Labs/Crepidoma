#!/usr/bin/env python3
"""Run gates quietly: one line per task, failure excerpt only on failure.

Usage: gate_runner.py {run TASK [TASK...] [--keep-going] | quiet -- CMD...}

`run` executes `task <name>` per TASK and prints `PASS name 3.2s` or `FAIL name 3.2s` plus at
most 12 failure lines. Stops at the first failure unless `--keep-going`.
`quiet` runs one command; success prints `ok (Ns)`, failure prints the excerpt.
Exit codes: 0 ok, 1 failure (quiet: the command's code), 2 usage error, 127 command not found.
"""

import argparse
import re
import shlex
import shutil
import subprocess
import sys
import time

MAX_LINES = 12
MAX_WIDTH = 200
DECISIVE = re.compile(r"error|fail|FAILED|^E  |Traceback", re.IGNORECASE)


def run(cmd: list[str]) -> tuple[int, str]:
    """Run cmd; return exit code and combined output."""
    binary = shutil.which(cmd[0]) or cmd[0]
    try:
        result = subprocess.run(
            [binary, *cmd[1:]],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except FileNotFoundError:
        return 127, f"{cmd[0]}: executable file not found"
    return result.returncode, result.stdout + result.stderr


def excerpt(output: str, limit: int = MAX_LINES) -> list[str]:
    """Lines that say why a run failed, else its last lines; at most limit."""
    lines = [line.rstrip()[:MAX_WIDTH] for line in output.splitlines() if line.strip()]
    hits = [line for line in lines if DECISIVE.search(line)]
    return hits[:limit] if hits else lines[-limit:]


def timed(cmd: list[str]) -> tuple[int, str, float]:
    started = time.monotonic()
    code, output = run(cmd)
    return code, output, time.monotonic() - started


def run_tasks(names: list[str], keep_going: bool) -> int:
    failed = False
    for name in names:
        code, output, seconds = timed(["task", *shlex.split(name)])
        if code == 0:
            print(f"PASS {name} {seconds:.1f}s")
            continue
        failed = True
        print(f"FAIL {name} {seconds:.1f}s")
        for line in excerpt(output):
            print(line)
        if not keep_going:
            break
    return 1 if failed else 0


def run_quiet(cmd: list[str]) -> int:
    code, output, seconds = timed(cmd)
    if code == 0:
        print(f"ok ({seconds:.1f}s)")
        return 0
    for line in excerpt(output):
        print(line)
    return code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=(__doc__ or "").partition("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    runner = sub.add_parser("run", help="run `task NAME` for each TASK")
    runner.add_argument("tasks", nargs="+")
    runner.add_argument("--keep-going", action="store_true", help="run all tasks after a failure")
    quiet = sub.add_parser("quiet", help="run one command, print only the verdict")
    quiet.add_argument("cmd", nargs=argparse.REMAINDER, help="-- CMD...")
    return parser


def tolerate_unencodable() -> None:
    """Replace characters the console encoding cannot represent instead of raising."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(errors="replace")


def main(argv: list[str] | None = None) -> int:
    tolerate_unencodable()
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        return run_tasks(args.tasks, args.keep_going)
    cmd = args.cmd[1:] if args.cmd[:1] == ["--"] else args.cmd
    if not cmd:
        parser.error("quiet requires a command after --")
    return run_quiet(cmd)


if __name__ == "__main__":
    sys.exit(main())
