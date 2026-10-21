"""Project allowance burn rate from recorded usage samples.

Usage: python usage_rate.py record --percent P --window NAME [--resets-at ISO]
       python usage_rate.py project [--window NAME] [--ceiling 95] [--lookback-hours 2]
       python usage_rate.py live [--sample] [--task-minutes N] [--json] [--window NAME]
              [--ceiling 95]

`record` appends a timestamped sample to `usage_samples.jsonl` in the hook state dir.
`project` fits the slope across recent samples of one window instance (same `resets_at`) and
prints percent per hour and hours until the ceiling. Exit 0 ok, 1 not enough samples,
2 usage error, 3 the ceiling is projected before the window resets (or, with no known reset,
is projected at all).

`live` reads the usage endpoint (budget.py) instead of the log and projects every window, from
two rates: the average over the window's life so far (one reading is enough) and the recent
slope from the log (needs two samples of the same window). The recent rate wins when it exists.
`--sample` records the reading first, in the same log `record` writes. `--task-minutes N` asks
whether work of that length fits before the ceiling; it does not: exit 3.
"""

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import budget
from hooks import ROOT, state_dir

LOG_NAME = "usage_samples.jsonl"
DEFAULT_CEILING = 95.0
DEFAULT_LOOKBACK_HOURS = 2.0
MIN_SAMPLES = 2
EXIT_OK, EXIT_SHORT, EXIT_WAIT = 0, 1, 3
# A rate below this is noise: a barely opened window divides a small number by a smaller one.
MIN_RATE = 0.001


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


def window_samples(window: str, resets_at: str | None) -> list[tuple[datetime, float]]:
    """Logged samples of this instance of a window: yesterday's window shares only its name."""
    if not resets_at:
        return []
    return [(s["_at"], s["percent"]) for s in load(window) if s.get("resets_at") == resets_at]


def average_rate(row: dict) -> float | None:
    """Percent per minute over the life of the window so far."""
    length = budget.WINDOW_MINUTES.get(row["window"])
    left = row["seconds_until_reset"]
    if not length or left is None:
        return None
    elapsed = length - left / 60.0
    return row["utilization"] / elapsed if elapsed > 0 else None


def recent_rate(row: dict) -> float | None:
    points = window_samples(row["window"], row["resets_at"])
    if len(points) < MIN_SAMPLES:
        return None
    minutes = (points[-1][0] - points[0][0]).total_seconds() / 60.0
    return (points[-1][1] - points[0][1]) / minutes if minutes > 0 else None


def projection(row: dict, ceiling: float) -> dict:
    average, recent = average_rate(row), recent_rate(row)
    use_recent = recent is not None and recent > MIN_RATE
    rate = recent if use_recent else average
    headroom = ceiling - row["utilization"]
    minutes = None
    if headroom <= 0:
        minutes = 0.0
    elif rate is not None and rate > MIN_RATE:
        minutes = headroom / rate

    def rounded(value: float | None, digits: int) -> float | None:
        return None if value is None else round(value, digits)

    return {
        "window": row["window"],
        "label": row["label"],
        "utilization": row["utilization"],
        "ceiling": ceiling,
        "headroom": round(headroom, 1),
        "average_per_minute": rounded(average, 4),
        "recent_per_minute": rounded(recent, 4),
        "rate_used": rounded(rate, 4),
        "rate_source": "recent" if use_recent else "average",
        "minutes_to_ceiling": rounded(minutes, 1),
        "seconds_until_reset": row["seconds_until_reset"],
        "samples": len(window_samples(row["window"], row["resets_at"])),
    }


def verdict(projections: list[dict], task_minutes: float) -> tuple[dict | None, bool | None]:
    """The tightest window, and whether the work in hand fits before it reaches the ceiling."""
    timed = [p for p in projections if p["minutes_to_ceiling"] is not None]
    if not timed:
        return None, None
    tightest = min(timed, key=lambda p: p["minutes_to_ceiling"])
    if task_minutes <= 0:
        return tightest, None
    return tightest, tightest["minutes_to_ceiling"] >= task_minutes


def render(projections: list[dict], task_minutes: float) -> list[str]:
    lines = []
    for p in projections:
        rate = "unknown" if p["rate_used"] is None else f"{p['rate_used']:.2f}%/min"
        left = (
            "unknown"
            if p["minutes_to_ceiling"] is None
            else budget.span(int(p["minutes_to_ceiling"] * 60))
        )
        lines.append(
            f"{p['label']:<18} {p['utilization']:5.1f}%  burning {rate} ({p['rate_source']}, "
            f"{p['samples']} sample(s))  {left} of work before {p['ceiling']:g}%"
        )
    tightest, fits = verdict(projections, task_minutes)
    if tightest is None:
        lines.append("No window could be projected: sample now and again in a few minutes.")
    elif fits is not None:
        span = budget.span(int(abs(tightest["minutes_to_ceiling"] - task_minutes) * 60))
        verb = f"fits, {span} to spare" if fits else f"does NOT fit: {span} short"
        lines.append(f"A {task_minutes:g}-minute lane {verb} ({tightest['label']}).")
    return lines


def live(args: argparse.Namespace) -> int:
    payload, reason = budget.fetch()
    rows = budget.readings(payload, only=args.window) if payload is not None else []
    if not rows:
        reason = reason or "The usage endpoint reported no windows."
        if args.json:
            print(json.dumps({"ok": False, "reason": reason}))
        else:
            print(reason, file=sys.stderr)
        return EXIT_SHORT
    if args.sample:
        for row in rows:
            record(row["utilization"], row["window"], row["resets_at"])
    projections = [projection(row, args.ceiling) for row in rows]
    tightest, fits = verdict(projections, args.task_minutes)
    if args.json:
        print(
            json.dumps(
                {
                    "ok": True,
                    "ceiling": args.ceiling,
                    "task_minutes": args.task_minutes,
                    "fits": fits,
                    "tightest": tightest["window"] if tightest else None,
                    "windows": projections,
                }
            )
        )
    else:
        print("\n".join(render(projections, args.task_minutes)))
    return EXIT_WAIT if fits is False else EXIT_OK


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
    now_parser = sub.add_parser("live", help="project every window from the live usage reading")
    now_parser.add_argument("--window", action="append", choices=[k for k, _ in budget.WINDOWS])
    now_parser.add_argument("--ceiling", type=float, default=DEFAULT_CEILING)
    now_parser.add_argument("--sample", action="store_true", help="record the reading first")
    now_parser.add_argument("--task-minutes", type=float, default=0.0, help="does this much fit")
    now_parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "live":
        return live(args)
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
