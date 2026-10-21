#!/usr/bin/env python3
"""Claude usage windows against a ceiling: show, gate, wait.

Usage: budget.py {show [--json] | check [--ceiling N] | wait [--ceiling N] [--poll S] [--timeout S]}
       budget.py --json --ceiling N   (hook contract: ok, over_ceiling, wait_seconds, windows)
Every mode takes --window NAME (repeatable) to judge only those windows; `wait --window five_hour
--ceiling 20` blocks until a fresh session, where the weekly figure would hold the wait for days.

Exit codes: 0 under ceiling, 1 unknown, 2 usage error, 3 at or over ceiling.
Reads the undocumented OAuth usage endpoint with the token from the Claude credentials file.
The token is never printed and never placed in a subprocess argv.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from budget_view import row_line, span

USAGE_URL = "https://api.anthropic.com/api/oauth/usage"

WINDOWS = (
    ("five_hour", "Session (5 hour)"),
    ("seven_day", "Weekly (7 day)"),
    ("seven_day_opus", "Weekly Opus"),
    ("seven_day_sonnet", "Weekly Sonnet"),
)

# Each window's length: with its reset time, how far into itself a window already is.
WINDOW_MINUTES = {
    "five_hour": 5 * 60,
    "seven_day": 7 * 24 * 60,
    "seven_day_opus": 7 * 24 * 60,
    "seven_day_sonnet": 7 * 24 * 60,
}

DEFAULT_CEILING = 95.0
DEFAULT_POLL = 300
# The endpoint answers 429 to a tight poll.
MIN_POLL = 60
UNDER, ERROR, OVER = 0, 1, 3
NO_WINDOWS = "The usage endpoint reported no windows."


def credentials_path() -> Path:
    return Path.home() / ".claude" / ".credentials.json"


def token() -> str | None:
    try:
        data = json.loads(credentials_path().read_text(encoding="utf-8"))
        return data.get("claudeAiOauth", {}).get("accessToken") or None
    except (OSError, ValueError, AttributeError):
        return None


def fetch() -> tuple[dict | None, str]:
    """The usage payload, or None and the reason it could not be read."""
    access = token()
    if access is None:
        return None, "No OAuth access token in the credentials file."
    request = urllib.request.Request(
        USAGE_URL,
        headers={"Authorization": "Bearer " + access, "Content-Type": "application/json"},
    )
    if not USAGE_URL.startswith("https://"):
        return None, "Usage URL must be https."
    try:
        # USAGE_URL is a module constant checked above; never a caller-supplied scheme.
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310  # nosemgrep
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        if error.code == 401:
            return None, "401: access token expired. Run any `claude` command, then retry."
        if error.code == 429:
            return None, "429: usage endpoint rate-limiting. Not an exhausted allowance."
        return None, f"HTTP {error.code} from the usage endpoint."
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as error:
        return None, f"Could not read the usage endpoint: {error}"
    if not isinstance(payload, dict):
        return None, "Usage endpoint returned an unexpected shape."
    return payload, ""


def parse_reset(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def readings(
    payload: dict, now: datetime | None = None, only: list[str] | None = None
) -> list[dict]:
    """One row per window the payload reports (or only those named); absent is skipped, not zero."""
    now = now or datetime.now(UTC)
    rows = []
    for key, label in WINDOWS:
        if only and key not in only:
            continue
        window = payload.get(key)
        if not isinstance(window, dict):
            continue
        used = window.get("utilization")
        if isinstance(used, bool) or not isinstance(used, (int, float)):
            continue
        reset = parse_reset(window.get("resets_at"))
        rows.append(
            {
                "window": key,
                "label": label,
                "utilization": float(used),
                "resets_at": reset.isoformat() if reset else None,
                "seconds_until_reset": (
                    max(0, int((reset - now).total_seconds())) if reset else None
                ),
            }
        )
    return rows


def breached(rows: list[dict], ceiling: float) -> list[dict]:
    return [row for row in rows if row["utilization"] >= ceiling]


def soonest_reset(rows: list[dict]) -> int:
    waits = [row["seconds_until_reset"] for row in rows if row["seconds_until_reset"] is not None]
    return min(waits) if waits else DEFAULT_POLL


def load(only: list[str] | None = None) -> tuple[list[dict] | None, str]:
    payload, reason = fetch()
    if payload is None:
        return None, reason
    rows = readings(payload, only=only)
    if not rows:
        return None, NO_WINDOWS
    return rows, ""


def unreadable(args: argparse.Namespace, reason: str) -> int:
    if args.json:
        print(json.dumps({"ok": False, "reason": reason}))
    else:
        print(reason, file=sys.stderr)
    return ERROR


def show(args: argparse.Namespace) -> int:
    rows, reason = load(args.window)
    if rows is None:
        return unreadable(args, reason)
    if args.json:
        print(json.dumps({"ok": True, "windows": rows}))
        return UNDER
    for row in rows:
        print(row_line(row))
    return UNDER


def check(args: argparse.Namespace) -> int:
    rows, reason = load(args.window)
    if rows is None:
        return unreadable(args, reason)
    over = breached(rows, args.ceiling)
    if args.json:
        print(
            json.dumps(
                {
                    "ok": True,
                    "ceiling": args.ceiling,
                    "over_ceiling": bool(over),
                    "breached": [row["window"] for row in over],
                    "wait_seconds": soonest_reset(over) if over else 0,
                    "windows": rows,
                }
            )
        )
    elif over:
        names = ", ".join(row["window"] for row in over)
        print(f"over {args.ceiling:g}%: {names}; reset in {span(soonest_reset(over))}")
    else:
        print(f"under {args.ceiling:g}%")
    return OVER if over else UNDER


def finish(args: argparse.Namespace) -> int:
    """The deadline arrived: one last read decides, so a window that just cleared is not over."""
    rows, reason = load(args.window)
    if rows is None:
        print(f"timed out; usage unknown: {reason}", file=sys.stderr)
        return ERROR
    over = breached(rows, args.ceiling)
    if not over:
        print(f"under {args.ceiling:g}%")
        return UNDER
    print("timed out still over the ceiling", file=sys.stderr)
    return OVER


def wait(args: argparse.Namespace) -> int:
    poll = max(MIN_POLL, args.poll)
    deadline = time.monotonic() + args.timeout if args.timeout else None
    while True:
        rows, reason = load(args.window)
        if rows is None and reason == NO_WINDOWS:
            # No window to wait on (bad filter or changed payload): waiting cannot help.
            print(reason, file=sys.stderr)
            return ERROR
        if rows is None:
            # A failed read is not an exhausted allowance: report and keep waiting.
            print(f"waiting: {reason}", file=sys.stderr, flush=True)
            nap = poll
        else:
            over = breached(rows, args.ceiling)
            if not over:
                print(f"under {args.ceiling:g}%")
                return UNDER
            nap = max(MIN_POLL, min(poll, soonest_reset(over) + 30))
            names = ", ".join(row["window"] for row in over)
            print(f"over {args.ceiling:g}%: {names}; next check in {span(nap)}", flush=True)
        if deadline is not None:
            left = deadline - time.monotonic()
            # Too little time to poll again is the deadline arriving; never poll under the floor.
            if left <= MIN_POLL:
                if left > 0:
                    time.sleep(left)
                return finish(args)
            nap = min(nap, int(left))
        time.sleep(nap)


def add_window(parser: argparse.ArgumentParser, default: object) -> None:
    keys = [key for key, _ in WINDOWS]
    parser.add_argument("--window", action="append", choices=keys, default=default)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Claude usage windows against a ceiling.")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--ceiling", type=float, default=DEFAULT_CEILING, help="percent (95)")
    add_window(parser, None)
    commands = parser.add_subparsers(dest="command")

    # SUPPRESS keeps a subcommand from overwriting a flag given before it.
    sub_show = commands.add_parser("show", help="one line per window")
    sub_show.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    add_window(sub_show, argparse.SUPPRESS)

    sub_check = commands.add_parser("check", help="exit 0 under, 3 over, 1 unknown")
    sub_check.add_argument("--ceiling", type=float, default=argparse.SUPPRESS)
    sub_check.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    add_window(sub_check, argparse.SUPPRESS)

    sub_wait = commands.add_parser("wait", help="block until under the ceiling")
    sub_wait.add_argument("--ceiling", type=float, default=argparse.SUPPRESS)
    add_window(sub_wait, argparse.SUPPRESS)
    sub_wait.add_argument("--poll", type=int, default=DEFAULT_POLL, help="seconds between reads")
    sub_wait.add_argument(
        "--timeout", type=int, default=0, help="give up after S seconds (0 = never)"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "show":
        return show(args)
    if args.command == "wait":
        return wait(args)
    return check(args)


if __name__ == "__main__":
    sys.exit(main())
