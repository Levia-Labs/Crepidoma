"""Rendering for budget.py: spans, labels, pacing and the usage table."""


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


def label(window: str) -> str:
    return LABELS.get(window, window)


def pace(
    utilization: float, seconds_until_reset: int | None, window_seconds: int
) -> tuple[float, float] | None:
    """Burnout and estimate for one window; None when its reset is unknown.

    Burnout is usage minus the share of the window already elapsed: 0 is ideal pace, positive
    burns faster than the quota refills. The estimate is that gap in hours of the window:
    negative is how long usage must stop for the clock to catch up (work ends that much
    earlier), positive is slack that can still be spent. Both are 0 at ideal pace.
    """
    if seconds_until_reset is None:
        return None
    elapsed = max(0, window_seconds - seconds_until_reset)
    burnout = utilization - 100 * elapsed / window_seconds
    return burnout, -burnout * window_seconds / 100 / 3600


RED, GREEN, PLAIN = "\x1b[31m", "\x1b[32m", "\x1b[0m"


HEADER = ("T", "used", "reset", "est.", "recomm.")
TINTED = (HEADER.index("est."), HEADER.index("recomm."))
# Right-aligned, percentages line up on "%" and clock() slots line up on d, h and m.
RIGHT = {HEADER.index("used"), HEADER.index("reset")}


def clock(seconds: int | None) -> str:
    """A duration in fixed-width slots ("3d 14h  0m", " 4h  8m") for a right-aligned column."""
    if seconds is None:
        return "unknown"
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    day = f"{days}d " if days else ""
    hour = f"{hours:2d}h " if days or hours else ""
    return f"{day}{hour}{rest // 60:2d}m"


def cells(row: dict) -> tuple[str, ...]:
    burnout, estimate = row["burnout"], row["estimate_hours"]
    advice = "n/a" if burnout is None else "SLOW DOWN" if burnout > 0 else "SPEED UP"
    return (
        label(row["window"]),
        f"{row['utilization']:.1f}%",
        clock(row["seconds_until_reset"]),
        "n/a" if estimate is None else f"{estimate:+.1f} h",
        advice,
    )


def table(rows: list[dict], colour: bool = False) -> list[str]:
    """Header plus one line per window, columns padded to line up, advice coloured by pace.

    Burnout stays out of the table: its sign always matches the estimate's, which reads in hours.
    Headers stay left-aligned; values in RIGHT columns line up on their right edge.
    """
    lines = [HEADER, *(cells(row) for row in rows)]
    # The last column is never padded, so a coloured cell carries no trailing spaces.
    widths = [max(len(line[i]) for line in lines) for i in range(len(HEADER) - 1)] + [0]
    out = []
    for line, row in zip(lines, [None, *rows], strict=True):
        padded = [
            cell.rjust(width) if row and i in RIGHT else cell.ljust(width)
            for i, (cell, width) in enumerate(zip(line, widths, strict=True))
        ]
        # Colour after padding: escape codes have no width but count in len().
        if colour and row and row["burnout"] is not None:
            tint = RED if row["burnout"] > 0 else GREEN
            for i in TINTED:
                padded[i] = f"{tint}{padded[i]}{PLAIN}"
        out.append(" | ".join(padded).rstrip())
    return out
