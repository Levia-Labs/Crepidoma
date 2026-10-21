"""Rendering for budget.py: spans, labels, the usage bar and tab-separated rows."""

import math
from datetime import datetime, tzinfo


def span(seconds: int | None) -> str:
    if seconds is None:
        return "unknown"
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {rest // 60}m"
    return f"{rest // 60}m"


LABELS = {"five_hour": "5h", "seven_day": "7d"}
BAR_CELLS = 10


def label(window: str) -> str:
    return LABELS.get(window, window)


def bar(percent: float) -> str:
    # Half up, not round(): banker's rounding would show 5% as empty and 25% as two cells.
    used = max(0, min(BAR_CELLS, math.floor(percent / 10 + 0.5)))
    return "[" + "#" * used + "." * (BAR_CELLS - used) + "]"


def local_stamp(iso: str, tz: tzinfo | None = None) -> str:
    return datetime.fromisoformat(iso).astimezone(tz).strftime("%Y-%m-%d %H:%M")


def row_line(row: dict, tz: tzinfo | None = None) -> str:
    when = "unknown"
    if row["resets_at"]:
        when = f"{local_stamp(row['resets_at'], tz)} ({span(row['seconds_until_reset'])})"
    pct = f"{row['utilization']:.1f}%"
    return "\t".join((label(row["window"]), pct, bar(row["utilization"]), "resets", when))
