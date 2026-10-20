"""Project allowance burn rate from recorded usage samples.

Usage: python usage_rate.py record --percent P --window NAME [--resets-at ISO]
       python usage_rate.py project [--window NAME] [--ceiling 95] [--lookback-hours 2]

`record` appends a timestamped sample to `usage_samples.jsonl` in the hook state dir.
`project` fits the slope across recent samples of one window instance (same `resets_at`) and
prints percent per hour and hours until the ceiling. Exit 0 ok, 1 not enough samples,
2 usage error, 3 the ceiling is projected before the window resets (or, with no known reset,
is projected at all).
"""

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from hooks import ROOT, state_dir

LOG_NAME = "usage_samples.jsonl"
DEFAULT_CEILING = 95.0
DEFAULT_LOOKBACK_HOURS = 2.0
MIN_SAMPLES = 2
EXIT_OK, EXIT_SHORT, EXIT_WAIT = 0, 1, 3


def now() -> datetime:
    return datetime.now(UTC)


def log_path() -> Path:
    return state_dir(ROOT) / LOG_NAME


def parse_time(text: str) -> datetime:
    value = datetime.fromisoformat(text)
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def record(percent: float, window: str, resets_at: str | None) -> Path:
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {"at": now().isoformat(), "window": window, "percent": percent}
    if resets_at:
        entry["resets_at"] = parse_time(resets_at).isoformat()
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(entry) + "\n")
    return path


def load(window: str | None) -> list[dict]:
    path = log_path()
    if not path.is_file():
        return []
    found = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            entry = json.loads(line)
            entry["_at"] = parse_time(entry["at"])
            entry["percent"] = float(entry["percent"])
        except (ValueError, KeyError, TypeError):
            continue
        if window is None or entry.get("window") == window:
            found.append(entry)
    return sorted(found, key=lambda e: e["_at"])


def recent(samples: list[dict], lookback_hours: float) -> list[dict]:
    """Samples of the newest window instance inside the lookback."""
    if not samples:
        return []
    newest = samples[-1]
    cutoff = now() - timedelta(hours=lookback_hours)
    return [
        s
        for s in samples
        if s["_at"] >= cutoff
        and s.get("window") == newest.get("window")
        and s.get("resets_at") == newest.get("resets_at")
    ]


def project(window: str | None, ceiling: float, lookback_hours: float) -> tuple[int, str]:
    points = recent(load(window), lookback_hours)
    if len(points) < MIN_SAMPLES:
        return EXIT_SHORT, f"insufficient samples: {len(points)} of {MIN_SAMPLES}"
    first, last = points[0], points[-1]
    hours = (last["_at"] - first["_at"]).total_seconds() / 3600
    if hours <= 0:
        return EXIT_SHORT, "insufficient samples: zero time span"
    rate = (last["percent"] - first["percent"]) / hours
    name = last.get("window")
    if last["percent"] >= ceiling:
        to_ceiling = 0.0
    elif rate <= 0:
        return EXIT_OK, f"{name}: {last['percent']:g}% rate {rate:.2f}%/h ceiling not projected"
    else:
        to_ceiling = (ceiling - last["percent"]) / rate
    until_reset = None
    if last.get("resets_at"):
        until_reset = (parse_time(last["resets_at"]) - now()).total_seconds() / 3600
    hits = until_reset is None or to_ceiling < until_reset
    line = (
        f"{name}: {last['percent']:g}% rate {rate:.2f}%/h ceiling {ceiling:g}% in {to_ceiling:.2f}h"
    )
    if until_reset is not None:
        line += f" reset in {max(until_reset, 0):.2f}h"
    return (EXIT_WAIT if hits else EXIT_OK), line + (" HIT" if hits else " ok")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Project allowance burn rate.")
    sub = parser.add_subparsers(dest="command", required=True)
    rec = sub.add_parser("record", help="append a usage sample")
    rec.add_argument("--percent", type=float, required=True)
    rec.add_argument("--window", required=True)
    rec.add_argument("--resets-at", help="ISO time the window resets")
    proj = sub.add_parser("project", help="project time to the ceiling")
    proj.add_argument("--window")
    proj.add_argument("--ceiling", type=float, default=DEFAULT_CEILING)
    proj.add_argument("--lookback-hours", type=float, default=DEFAULT_LOOKBACK_HOURS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "record":
        try:
            record(args.percent, args.window, args.resets_at)
        except ValueError as error:
            print(f"bad --resets-at: {error}", file=sys.stderr)
            return 2
        print(f"recorded {args.window} {args.percent:g}%")
        return EXIT_OK
    code, line = project(args.window, args.ceiling, args.lookback_hours)
    print(line)
    return code


if __name__ == "__main__":
    sys.exit(main())
