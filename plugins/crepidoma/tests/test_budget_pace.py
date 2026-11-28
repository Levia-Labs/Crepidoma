import json

import budget
import budget_view
import pytest
from test_budget import patch_fetch, payload

HOUR = 3600
WEEK = 7 * 24 * HOUR


def test_pace_on_schedule_is_zero():
    # Half the week gone, half the quota used: ideal pace, nothing to correct.
    assert budget_view.pace(50.0, WEEK // 2, WEEK) == (0.0, 0.0)


def test_pace_ahead_of_schedule_must_stop_early():
    # 62% used with 86h left of 168h: 82h elapsed, so 48.8% expected.
    burnout, estimate = budget_view.pace(62.0, 86 * HOUR, WEEK)
    assert burnout == pytest.approx(62.0 - 100 * 82 / 168)
    # 13.2% over pace is 22.2h of the week: usage stops that long for the clock to catch up.
    assert estimate == pytest.approx(-22.16, abs=0.01)


def test_pace_behind_schedule_leaves_quota_at_reset():
    burnout, estimate = budget_view.pace(2.0, 4 * HOUR + 35 * 60, 5 * HOUR)
    assert burnout < 0
    assert estimate > 0


def test_pace_unknown_reset_is_none():
    assert budget_view.pace(10.0, None, WEEK) is None


def test_pace_idle_estimate_is_time_elapsed():
    # Nothing used half way through: all 84 elapsed hours are slack.
    assert budget_view.pace(0.0, WEEK // 2, WEEK) == (-50.0, 84.0)


def test_pace_used_at_window_start_is_all_overuse():
    assert budget_view.pace(10.0, WEEK, WEEK) == (10.0, pytest.approx(-16.8))


@pytest.mark.parametrize("used", [0.5, 5.0, 25.0, 49.9, 50.1, 75.0, 99.0, 100.0, 120.0])
@pytest.mark.parametrize("left", [1, HOUR, WEEK // 4, WEEK // 2, WEEK - HOUR])
def test_pace_estimate_is_burnout_in_window_hours(used, left):
    burnout, estimate = budget_view.pace(used, left, WEEK)
    assert estimate == pytest.approx(-burnout * 168 / 100)
    assert (burnout > 0) == (estimate < 0)


def row(window="five_hour", used=5.0, left=4 * HOUR + 14 * 60, burnout=-10.1, estimate=10.1):
    return {
        "window": window,
        "utilization": used,
        "seconds_until_reset": left,
        "burnout": burnout,
        "estimate_hours": estimate,
    }


def test_table_header_and_rows_line_up():
    lines = budget_view.table([row(), row("seven_day", 63.0, 86 * HOUR, 14.5, -38.8)])
    assert lines == [
        "T  | used  | reset      | est.    | recomm.",
        "5h |  5.0% |     4h 14m | +10.1 h | SPEED UP",
        "7d | 63.0% | 3d 14h  0m | -38.8 h | SLOW DOWN",
    ]


@pytest.mark.parametrize(
    ("seconds", "text"),
    [
        (None, "unknown"),
        (8 * 60, " 8m"),
        (4 * HOUR + 8 * 60, " 4h  8m"),
        (86 * HOUR, "3d 14h  0m"),
        (10 * 24 * HOUR + 2 * HOUR, "10d  2h  0m"),
    ],
)
def test_clock_pads_units_to_fixed_slots(seconds, text):
    # Right-aligned in the column, fixed-width slots put each d, h and m in the same place.
    assert budget_view.clock(seconds) == text


def test_table_colours_estimate_by_pace():
    under, over = budget_view.table(
        [row(), row("seven_day", burnout=14.5, estimate=-38.8)], colour=True
    )[1:]
    assert under.endswith("| \x1b[32m+10.1 h\x1b[0m | \x1b[32mSPEED UP\x1b[0m")
    assert over.endswith("| \x1b[31m-38.8 h\x1b[0m | \x1b[31mSLOW DOWN\x1b[0m")


def test_table_unknown_reset():
    lines = budget_view.table([row(left=None, burnout=None, estimate=None)])
    assert lines[1] == "5h | 5.0% | unknown | n/a  | n/a"


def test_show_prints_table_without_colour_when_piped(monkeypatch, capsys):
    patch_fetch(monkeypatch, (payload(five=42.5), ""))
    assert budget.main(["show"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 3
    assert lines[0].startswith("T  | used")
    assert lines[1].startswith("5h | 42.5%")
    assert lines[2].startswith("7d | 20.0%")
    assert "\x1b[" not in "".join(lines)


def test_show_json_carries_pace(monkeypatch, capsys):
    patch_fetch(monkeypatch, (payload(five=42.5, hours=2), ""))
    assert budget.main(["show", "--json"]) == 0
    five = json.loads(capsys.readouterr().out)["windows"][0]
    # 3h of 5h gone: 60% expected against 42.5% used.
    assert five["burnout"] == pytest.approx(-17.5, abs=0.1)
    assert five["estimate_hours"] > 0
