"""Ship a PR end to end: resolve, un-stale, check conflicts, wait for checks, squash-merge, tidy.

Usage: land.py [PR] [--repo OWNER/NAME] [--timeout S]
One output line per phase, at most 20 lines. Exit 0 merged, 1 otherwise.
The command runner is injected (`Runner`) so tests drive a fake gh/git.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from collections.abc import Callable

Runner = Callable[[list[str]], tuple[int, str]]
MAX_LINES = 20
LOG_CAP = 10
WATCH_LIMIT = 3600
DECISIVE = re.compile(r"error|fail|assert|exception|panic|traceback|denied|✗|not found", re.I)
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


class Land(Exception):
    """A phase failed; the message is the final output line."""


def system_run(args: list[str]) -> tuple[int, str]:
    p = subprocess.run(
        args, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False
    )
    return p.returncode, p.stdout + (p.stderr if p.returncode else "")


def parse_json(text: str):
    try:
        return json.loads(text)
    except ValueError:
        return None


def decisive_lines(log: str, cap: int = LOG_CAP) -> list[str]:
    """Return at most `cap` log lines that name the failure, falling back to the tail."""
    lines = [ANSI.sub("", ln).strip() for ln in log.splitlines()]
    lines = [ln.split("\t")[-1] for ln in lines if ln]
    hits = [ln[:200] for ln in lines if DECISIVE.search(ln)]
    return (hits or [ln[:200] for ln in lines])[-cap:]


def dedupe_checks(data: list[dict]) -> list[dict]:
    """Keep one entry per check name: the most recent run, else the higher job id."""

    def rank(check: dict) -> tuple[str, int]:
        stamp = str(check.get("completedAt") or check.get("startedAt") or "")
        job = re.search(r"/job/(\d+)", str(check.get("link", "")))
        return (stamp if not stamp.startswith("0001") else "", int(job.group(1)) if job else 0)

    best: dict[str, dict] = {}
    for check in data:
        if not isinstance(check, dict):
            continue
        name = str(check.get("name", "?"))
        if name not in best or rank(check) >= rank(best[name]):
            best[name] = check
    return list(best.values())


class Lander:
    def __init__(self, run: Runner, sleep: Callable[[float], None], repo: str | None):
        self.run, self.sleep, self.repo = run, sleep, repo
        self.lines: list[str] = []

    def say(self, line: str) -> None:
        if len(self.lines) < MAX_LINES:
            self.lines.append(line)

    def gh(self, args: list[str]) -> tuple[int, str]:
        return self.run(["gh", *args, *(["-R", self.repo] if self.repo else [])])

    def view(self, pr: str | None, fields: str) -> dict:
        rc, out = self.gh(["pr", "view", *([pr] if pr else []), "--json", fields])
        data = parse_json(out)
        if rc != 0 or not isinstance(data, dict):
            raise Land(f"resolve: no PR found ({out.strip().splitlines()[:1] or 'gh failed'})")
        return data

    def remote_head(self, branch: str) -> str:
        remote = f"https://github.com/{self.repo}.git" if self.repo else "origin"
        _, out = self.run(["git", "ls-remote", remote, f"refs/heads/{branch}"])
        return out.split()[0] if out.split() else ""

    def is_stale(self, pr: dict) -> bool:
        return self.remote_head(pr["headRefName"]) not in ("", pr["headRefOid"])

    def refresh(self, pr: dict) -> dict:
        """Close and reopen once when the PR head lags the branch, then re-check."""
        if not self.is_stale(pr):
            self.say("head: current")
            return pr
        num = str(pr["number"])
        self.gh(["pr", "close", num])
        self.gh(["pr", "reopen", num])
        pr = self.view(num, PR_FIELDS)
        if self.is_stale(pr):
            raise Land("head: stale after close/reopen; push the branch again or wait, then rerun")
        self.say("head: stale, reopened, now current")
        return pr

    def check_mergeable(self, pr: dict) -> None:
        state = pr.get("mergeable")
        if state == "CONFLICTING":
            raise Land("conflicts: mergeable CONFLICTING; merge origin/main into the branch, push")
        self.say(f"mergeable: {str(state).lower()}")

    def checks(self, num: str) -> list[dict]:
        fields = "name,bucket,link,startedAt,completedAt"
        _rc, out = self.gh(["pr", "checks", num, "--json", fields])
        data = parse_json(out)
        return dedupe_checks(data) if isinstance(data, list) else []

    def annotation(self, link: str, job: str) -> str:
        """First annotation message of the check run behind a job, or ''."""
        found = re.search(r"github\.com/([^/]+/[^/]+)/", link)
        slug = self.repo or (found.group(1) if found else "{owner}/{repo}")
        rc, out = self.run(["gh", "api", f"repos/{slug}/check-runs/{job}/annotations"])
        data = parse_json(out)
        if rc != 0 or not isinstance(data, list):
            return ""
        for item in data:
            msg = str(item.get("message") or "").strip() if isinstance(item, dict) else ""
            if msg:
                return msg.splitlines()[0][:200]
        return ""

    def wait_registered(self, num: str, timeout: float) -> list[dict]:
        waited, delay = 0.0, 5.0
        while True:
            found = self.checks(num)
            if found:
                self.say(f"checks: {len(found)} registered after {int(waited)}s")
                return found
            if waited >= timeout:
                raise Land(f"checks: none registered within {int(timeout)}s")
            self.sleep(delay)
            waited += delay
            delay = min(delay * 2, 30.0)

    def wait_done(self, num: str, found: list[dict]) -> list[dict]:
        waited = 0.0
        while any(c.get("bucket") == "pending" for c in found) and waited < WATCH_LIMIT:
            self.sleep(15.0)
            waited += 15.0
            found = self.checks(num) or found
        if any(c.get("bucket") == "pending" for c in found):
            raise Land("checks: still pending after watch limit")
        return found

    def failure_logs(self, failed: list[dict]) -> None:
        names = ", ".join(c.get("name", "?") for c in failed)
        self.say(f"checks: FAILED {len(failed)}: {names}")
        for check in failed:
            match = re.search(r"/job/(\d+)", check.get("link", ""))
            self.say(f"  {check.get('name', '?')}")
            if not match:
                continue
            job = match.group(1)
            rc, log = self.gh(["run", "view", "--job", job, "--log-failed"])
            if rc != 0 or not log.strip() or log.lstrip().startswith("log not found"):
                note = self.annotation(check.get("link", ""), job)
                self.say(f"    {note or 'no log or annotation'}")
                continue
            room = max(0, min(LOG_CAP, MAX_LINES - len(self.lines) - 1))
            for ln in decisive_lines(log, room):
                self.say(f"    {ln}")
        raise Land("land: not merged")

    def default_branch(self) -> str:
        _, ref = self.run(["git", "symbolic-ref", "refs/remotes/origin/HEAD"])
        prefix = "refs/remotes/origin/"
        ref = ref.strip()
        return ref[len(prefix) :] if ref.startswith(prefix) and len(ref) > len(prefix) else "main"

    def tidy(self, num: str, branch: str) -> None:
        """Update the default branch and delete the PR branch; MERGED state, not ancestry."""
        state = self.view(num, "state").get("state")
        default = self.default_branch()
        rc, out = self.run(["git", "switch", default])
        if rc == 0:
            rc, out = self.run(["git", "pull", "--ff-only", "--prune"])
        self.say(
            f"local: {default} updated" if rc == 0 else f"local: update failed: {out.strip()[:120]}"
        )
        if state != "MERGED" or branch == default:
            self.say(f"branch: kept ({state})")
            return
        rc, out = self.run(["git", "branch", "-D", branch])
        self.say(f"branch: deleted {branch}" if rc == 0 else f"branch: {out.strip()[:120]}")

    def land(self, pr_arg: str | None, timeout: float) -> int:
        try:
            pr = self.view(pr_arg, PR_FIELDS)
            num, branch = str(pr["number"]), pr["headRefName"]
            self.say(f"resolve: #{num} {branch}")
            pr = self.refresh(pr)
            self.check_mergeable(pr)
            found = self.wait_done(num, self.wait_registered(num, timeout))
            failed = [c for c in found if c.get("bucket") in ("fail", "cancel")]
            if failed:
                self.failure_logs(failed)
            self.say("checks: passed")
            rc, out = self.gh(["pr", "merge", num, "--squash"])
            if rc != 0:
                raise Land(f"merge: failed: {out.strip()[:160]}")
            self.say("merge: squashed")
            self.tidy(num, branch)
            return 0
        except Land as stop:
            self.say(str(stop))
            return 1


PR_FIELDS = "number,headRefName,headRefOid,mergeable,state"


def main(argv: list[str] | None = None, run: Runner = system_run, sleep=time.sleep) -> int:
    parser = argparse.ArgumentParser(prog="land")
    parser.add_argument("pr", nargs="?")
    parser.add_argument("--repo")
    parser.add_argument("--timeout", type=float, default=300.0)
    args = parser.parse_args(argv)
    lander = Lander(run, sleep, args.repo)
    code = lander.land(args.pr, args.timeout)
    print("\n".join(lander.lines))
    return code


if __name__ == "__main__":
    sys.exit(main())
