import json
from datetime import UTC, datetime, timedelta

import budget
import pytest


def payload(five=10.0, seven=20.0, hours=2):
    reset = (datetime.now(UTC) + timedelta(hours=hours)).isoformat()
    return {
        "five_hour": {"utilization": five, "resets_at": reset},
        "seven_day": {"utilization": seven, "resets_at": reset},
        "seven_day_opus": None,
    }


def patch_fetch(monkeypatch, value):
    monkeypatch.setattr(budget, "fetch", value if callable(value) else lambda: value)


def test_show_formats_one_line_per_window(monkeypatch, capsys):
    patch_fetch(monkeypatch, (payload(five=42.5), ""))
    assert budget.main(["show"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("five_hour 42.5% resets ")
    assert lines[1].startswith("seven_day 20.0% resets ")


def test_show_json(monkeypatch, capsys):
    patch_fetch(monkeypatch, (payload(), ""))
    assert budget.main(["show", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["ok"] is True
    assert [row["window"] for row in data["windows"]] == ["five_hour", "seven_day"]


@pytest.mark.parametrize(
    ("five", "ceiling", "code"),
    [(50.0, "95", 0), (95.0, "95", 3), (99.0, "95", 3), (50.0, "40", 3)],
)
def test_check_exit_codes(monkeypatch, capsys, five, ceiling, code):
    patch_fetch(monkeypatch, (payload(five=five), ""))
    assert budget.main(["check", "--ceiling", ceiling]) == code


def test_check_unknown_is_one(monkeypatch, capsys):
    patch_fetch(monkeypatch, (None, "no token"))
    assert budget.main(["check"]) == 1
    assert "no token" in capsys.readouterr().err


def test_check_empty_payload_is_one(monkeypatch):
    patch_fetch(monkeypatch, ({}, ""))
    assert budget.main(["check"]) == 1


def test_wait_loops_until_under(monkeypatch, capsys):
    answers = iter([(payload(five=99.0), ""), (None, "blip"), (payload(five=10.0), "")])
    patch_fetch(monkeypatch, lambda: next(answers))
    clock = {"slept": []}
    monkeypatch.setattr(budget.time, "sleep", clock["slept"].append)
    assert budget.main(["wait", "--ceiling", "95", "--poll", "300"]) == 0
    assert len(clock["slept"]) == 2
    assert all(budget.MIN_POLL <= nap <= 300 for nap in clock["slept"])


def test_json_contract_over(monkeypatch, capsys):
    patch_fetch(monkeypatch, (payload(five=97.0, hours=1), ""))
    assert budget.main(["--json", "--ceiling", "95"]) == 3
    data = json.loads(capsys.readouterr().out)
    assert data["ok"] is True
    assert data["over_ceiling"] is True
    assert 0 < data["wait_seconds"] <= 3600
    assert data["windows"][0]["label"] == "Session (5 hour)"
    assert data["windows"][0]["utilization"] == 97.0


def test_json_contract_under(monkeypatch, capsys):
    patch_fetch(monkeypatch, (payload(), ""))
    assert budget.main(["--json", "--ceiling", "95"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["ok"] is True
    assert data["over_ceiling"] is False
    assert data["wait_seconds"] == 0


def test_json_contract_unknown(monkeypatch, capsys):
    patch_fetch(monkeypatch, (None, "down"))
    assert budget.main(["--json", "--ceiling", "95"]) == 1
    assert json.loads(capsys.readouterr().out)["ok"] is False


def test_token_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(budget, "credentials_path", lambda: tmp_path / "none.json")
    assert budget.token() is None
    assert budget.fetch()[0] is None
