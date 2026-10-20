import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import usage_rate

START = datetime(2030, 1, 1, 12, 0, tzinfo=UTC)
RESET = (START + timedelta(hours=4)).isoformat()


@pytest.fixture
def clock(tmp_path: Path, monkeypatch):
    state = {"t": START}
    monkeypatch.setattr(usage_rate, "now", lambda: state["t"])
    monkeypatch.setattr(usage_rate, "state_dir", lambda root: tmp_path)
    return state


def sample(clock, minutes: float, percent: float, resets_at: str | None = None, window="five_hour"):
    clock["t"] = START + timedelta(minutes=minutes)
    argv = ["record", "--percent", str(percent), "--window", window]
    if resets_at:
        argv += ["--resets-at", resets_at]
    assert usage_rate.main(argv) == 0


def test_record_appends_jsonl(clock, tmp_path: Path):
    sample(clock, 0, 10)
    sample(clock, 5, 12)
    lines = (tmp_path / usage_rate.LOG_NAME).read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2


def test_not_enough_samples(clock, capsys):
    assert usage_rate.main(["project"]) == 1
    sample(clock, 0, 10)
    assert usage_rate.main(["project"]) == 1
    assert "insufficient" in capsys.readouterr().out


def test_hits_ceiling_before_reset(clock, capsys):
    reset = (START + timedelta(hours=3)).isoformat()
    sample(clock, 0, 10, reset)
    sample(clock, 60, 40, reset)
    capsys.readouterr()  # drop the record lines; only the projection is asserted
    assert usage_rate.main(["project", "--ceiling", "95"]) == 3
    out = capsys.readouterr().out
    assert "30.00%/h" in out
    assert "1.83h" in out
    assert len(out.splitlines()) == 1


def test_resets_before_ceiling(clock):
    reset = (START + timedelta(hours=1, minutes=30)).isoformat()
    sample(clock, 0, 10, reset)
    sample(clock, 60, 20, reset)
    assert usage_rate.main(["project"]) == 0


def test_flat_usage_is_ok(clock):
    sample(clock, 0, 20)
    sample(clock, 30, 20)
    assert usage_rate.main(["project"]) == 0


def test_old_samples_and_other_windows_ignored(clock):
    sample(clock, 0, 90, window="weekly")
    sample(clock, 1, 5)
    sample(clock, 200, 10)
    assert usage_rate.main(["project", "--window", "five_hour"]) == 1


def test_bad_resets_at(clock):
    assert usage_rate.main(["record", "--percent", "1", "--window", "w", "--resets-at", "x"]) == 2


def live_row(left=4 * 3600, used=30.0, resets_at=RESET):
    return {
        "window": "five_hour",
        "label": "Session (5 hour)",
        "utilization": used,
        "resets_at": resets_at,
        "seconds_until_reset": left,
    }


def test_average_rate_over_elapsed_window():
    assert usage_rate.average_rate(live_row()) == 0.5  # 60 minutes in, 30 percent used


def test_average_rate_unknown_at_window_start():
    assert usage_rate.average_rate(live_row(left=5 * 3600)) is None
    assert usage_rate.average_rate(live_row(left=None)) is None


def test_verdict_judges_by_the_tightest_window():
    roomy, tight = {"minutes_to_ceiling": 30}, {"minutes_to_ceiling": 5}
    assert usage_rate.verdict([], 10) == (None, None)
    assert usage_rate.verdict([roomy, tight], 10) == (tight, False)
    assert usage_rate.verdict([roomy], 30) == (roomy, True)
    assert usage_rate.verdict([roomy], 0) == (roomy, None)


def stub_live(monkeypatch, rows):
    payload = {row["window"]: {"utilization": row["utilization"]} for row in rows}
    monkeypatch.setattr(usage_rate.budget, "fetch", lambda: (payload, ""))
    monkeypatch.setattr(usage_rate.budget, "readings", lambda data, now=None, only=None: rows)


def test_live_sample_records_then_reports(clock, monkeypatch, tmp_path, capsys):
    stub_live(monkeypatch, [live_row()])
    assert usage_rate.main(["live", "--sample"]) == 0
    line = json.loads((tmp_path / usage_rate.LOG_NAME).read_text(encoding="utf-8"))
    assert (line["window"], line["percent"], line["resets_at"]) == ("five_hour", 30.0, RESET)
    assert "Session (5 hour)" in capsys.readouterr().out


def test_live_prefers_the_recent_rate(clock, monkeypatch, capsys):
    stub_live(monkeypatch, [live_row(used=20.0)])
    sample(clock, 0, 10, RESET)
    sample(clock, 10, 20, RESET)
    capsys.readouterr()
    assert usage_rate.main(["live", "--json"]) == 0
    row = json.loads(capsys.readouterr().out)["windows"][0]
    assert row["rate_source"] == "recent"
    assert row["recent_per_minute"] == 1.0
    assert row["samples"] == 2


def test_live_task_that_does_not_fit_exits_three(clock, monkeypatch, capsys):
    stub_live(monkeypatch, [live_row(used=90.0)])
    assert usage_rate.main(["live", "--task-minutes", "60", "--json"]) == 3
    data = json.loads(capsys.readouterr().out)
    assert data["fits"] is False
    assert data["tightest"] == "five_hour"


def test_live_unknown_allowance_is_one(clock, monkeypatch, capsys):
    monkeypatch.setattr(usage_rate.budget, "fetch", lambda: (None, "down"))
    assert usage_rate.main(["live", "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["ok"] is False
