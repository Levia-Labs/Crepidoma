from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import usage_rate

START = datetime(2030, 1, 1, 12, 0, tzinfo=UTC)


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
