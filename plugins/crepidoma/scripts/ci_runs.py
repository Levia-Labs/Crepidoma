"""Watch a CI run and read its failing-job errors, for this or another GitHub repo.

Usage: ci_runs.py watch [--repo O/R] [--sha SHA | --run ID] [--timeout S] [--interval S]
       ci_runs.py fail  [--repo O/R] [--sha SHA | --run ID] [--lines N]

watch: waits for the run of a commit to appear, watches it, prints one line per run.
  Exit 0 success, 1 run failed, 3 no run appeared within --timeout.
fail: prints each failed job (name, URL) and its error lines, ANSI stripped, at most
  --lines lines in total. Exit 1 failures printed, 0 none, 3 no run found.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
STAMP = re.compile(r"^\d{4}-\d\d-\d\dT[\d:.]+Z ?")
RUN_FIELDS = "databaseId,status,conclusion,url,workflowName"


def clean_line(line: str) -> str:
    return STAMP.sub("", ANSI.sub("", line)).rstrip()


def error_lines(text: str, cap: int) -> list[str]:
    seen: list[str] = []
    for raw in text.splitlines():
        line = clean_line(raw)
        if "error" in line.lower() and line not in seen:
            seen.append(line)
            if len(seen) >= cap:
                break
    return seen[:cap]


def failed_jobs(data: dict) -> list[dict]:
    return [j for j in data.get("jobs", []) if j.get("conclusion") == "failure"]


def gh(args: list[str]) -> tuple[int, str]:
    try:
        p = subprocess.run(
            ["gh", *args], capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
    except FileNotFoundError:
        return 127, "missing gh: install https://cli.github.com"
    return p.returncode, p.stdout if p.returncode == 0 else p.stdout + p.stderr


def repo_args(repo: str | None) -> list[str]:
    return ["-R", repo] if repo else []


def list_runs(repo: str | None, sha: str | None, extra: list[str]) -> list[dict]:
    args = ["run", "list", *repo_args(repo), "--json", RUN_FIELDS, *extra]
    if sha:
        args += ["--commit", sha]
    else:
        args += ["--limit", "1"]
    rc, out = gh(args)
    return json.loads(out) if rc == 0 and out.strip() else []


def run_line(run: dict) -> str:
    state = run.get("conclusion") or run.get("status")
    return f"run {run['databaseId']} {state} {run.get('workflowName', '')} {run.get('url', '')}"


def full_sha(repo: str | None, sha: str | None) -> str | None:
    if not sha or len(sha) >= 40:
        return sha
    repo = resolve_repo(repo)
    if not repo:
        return sha
    rc, out = gh(["api", f"repos/{repo}/commits/{sha}", "--jq", ".sha"])
    return out.strip() if rc == 0 and out.strip() else sha


def cmd_watch(a: argparse.Namespace) -> int:
    a.sha = full_sha(a.repo, a.sha)
    attempts = max(1, a.timeout // max(1, a.interval) + 1)
    runs: list[dict] = []
    for i in range(attempts):
        if a.run:
            rc, out = gh(["run", "view", a.run, *repo_args(a.repo), "--json", RUN_FIELDS])
            runs = [json.loads(out)] if rc == 0 else []
        else:
            runs = list_runs(a.repo, a.sha, [])
        if runs:
            break
        if i < attempts - 1:
            time.sleep(a.interval)
    if not runs:
        print(f"ci: no run for {a.sha or 'repo'} after {a.timeout}s")
        return 3
    worst = 0
    for run in runs:
        rid = str(run["databaseId"])
        if run.get("status") != "completed":
            gh(["run", "watch", rid, *repo_args(a.repo), "--exit-status"])
        rc, out = gh(["run", "view", rid, *repo_args(a.repo), "--json", RUN_FIELDS])
        final = json.loads(out) if rc == 0 else run
        print(run_line(final))
        if final.get("conclusion") != "success":
            worst = 1
    return worst


def find_failed_run(a: argparse.Namespace) -> str | None:
    a.sha = full_sha(a.repo, a.sha)
    if a.run:
        return a.run
    if a.sha:
        runs = [r for r in list_runs(a.repo, a.sha, []) if r.get("conclusion") == "failure"]
    else:
        runs = list_runs(a.repo, None, ["--status", "failure"])
    return str(runs[0]["databaseId"]) if runs else None


def resolve_repo(repo: str | None) -> str | None:
    if repo:
        return repo
    rc, out = gh(["repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"])
    return out.strip() if rc == 0 and out.strip() else None


def cmd_fail(a: argparse.Namespace) -> int:
    rid = find_failed_run(a)
    if not rid:
        print("ci: no failed run")
        return 3
    rc, out = gh(["run", "view", rid, *repo_args(a.repo), "--json", "jobs"])
    if rc != 0:
        print(f"ci: run view failed: {out.strip()[:200]}")
        return 1
    jobs = failed_jobs(json.loads(out))
    if not jobs:
        print("ci: no failed jobs")
        return 0
    repo = resolve_repo(a.repo)
    if not repo:
        print("ci: cannot resolve repo, pass --repo O/R")
        return 1
    left = a.lines
    for job in jobs:
        print(f"{job['name']} {job['url']}")
        rc, log = gh(
            [
                "api",
                f"repos/{repo}/actions/jobs/{job['databaseId']}/logs",
                "--allow-escape-sequences",
            ]
        )
        found = error_lines(log, left) if rc == 0 else [f"log unavailable: {log.strip()[:100]}"]
        for line in found:
            print(f"  {line}")
            left -= 1
        if left <= 0:
            break
    return 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ci_runs")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("watch", "fail"):
        s = sub.add_parser(name)
        s.add_argument("--repo", default=None)
        g = s.add_mutually_exclusive_group()
        g.add_argument("--sha", default=None)
        g.add_argument("--run", default=None)
        if name == "watch":
            s.add_argument("--timeout", type=int, default=300)
            s.add_argument("--interval", type=int, default=5)
        else:
            s.add_argument("--lines", type=int, default=20)
    return p


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    return cmd_watch(a) if a.cmd == "watch" else cmd_fail(a)


if __name__ == "__main__":
    sys.exit(main())
