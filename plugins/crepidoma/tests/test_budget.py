import json
from datetime import UTC, datetime, timedelta, timezone

import budget
import budget_auth
import budget_view
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
    first = lines[0].split("\t")
    second = lines[1].split("\t")
    assert first[:4] == ["5h", "resets", "42.5%", "[####......]"]
    assert second[:4] == ["7d", "resets", "20.0%", "[##........]"]
    assert len(first) == len(second) == 5


@pytest.mark.parametrize(
    ("percent", "bar"),
    [
        (0.0, "[..........]"),
        (3.0, "[..........]"),
        (5.0, "[#.........]"),
        (6.0, "[#.........]"),
        (25.0, "[###.......]"),
        (47.0, "[#####.....]"),
        (100.0, "[##########]"),
        (130.0, "[##########]"),
        (-5.0, "[..........]"),
    ],
)
def test_bar_rounds_and_clamps(percent, bar):
    assert budget_view.bar(percent) == bar


@pytest.mark.parametrize(
    ("window", "label"),
    [("five_hour", "5h"), ("seven_day", "7d"), ("seven_day_opus", "seven_day_opus")],
)
def test_label(window, label):
    assert budget_view.label(window) == label


def test_local_stamp_uses_given_zone():
    tz = timezone(timedelta(hours=2))
    assert budget_view.local_stamp("2026-10-21T12:20:00.120166+00:00", tz) == "2026-10-21 14:20"
    assert budget_view.local_stamp("2026-10-21T23:30:00+00:00", tz) == "2026-10-22 01:30"


def test_row_line_known_and_unknown_reset():
    tz = timezone(timedelta(hours=2))
    row = {
        "window": "five_hour",
        "utilization": 3.0,
        "resets_at": "2026-10-21T12:20:00+00:00",
        "seconds_until_reset": 4 * 3600 + 43 * 60,
    }
    assert (
        budget_view.row_line(row, tz) == "5h\tresets\t3.0%\t[..........]\t2026-10-21 14:20 (4h 43m)"
    )
    row.update(resets_at=None, seconds_until_reset=None)
    assert budget_view.row_line(row, tz) == "5h\tresets\t3.0%\t[..........]\tunknown"


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
    monkeypatch.setattr(budget_auth, "credentials_path", lambda: tmp_path / "none.json")
    monkeypatch.setattr(budget_auth, "keychain_credentials", lambda: None)
    assert budget_auth.token() is None
    assert budget.fetch()[0] is None


def test_token_falls_back_to_keychain(monkeypatch, tmp_path):
    monkeypatch.setattr(budget_auth, "credentials_path", lambda: tmp_path / "none.json")
    monkeypatch.setattr(
        budget_auth, "keychain_credentials", lambda: {"claudeAiOauth": {"accessToken": "kc"}}
    )
    assert budget_auth.token() == "kc"


def test_token_prefers_credentials_file(monkeypatch, tmp_path):
    cred = tmp_path / "cred.json"
    cred.write_text(json.dumps({"claudeAiOauth": {"accessToken": "file"}}), encoding="utf-8")
    monkeypatch.setattr(budget_auth, "credentials_path", lambda: cred)
    monkeypatch.setattr(
        budget_auth, "keychain_credentials", lambda: {"claudeAiOauth": {"accessToken": "kc"}}
    )
    assert budget_auth.token() == "file"


def test_window_filter_judges_only_the_named_window(monkeypatch):
    patch_fetch(monkeypatch, (payload(five=10.0, seven=99.0), ""))
    assert budget.main(["check", "--window", "five_hour"]) == 0
    assert budget.main(["check", "--window", "seven_day"]) == 3
    assert budget.main(["--json", "--window", "five_hour"]) == 0


def test_window_lengths_cover_every_window():
    assert {key for key, _ in budget.WINDOWS} == set(budget.WINDOW_MINUTES)
    assert budget.WINDOW_MINUTES["five_hour"] == 300


def test_wait_timeout_returns_over(monkeypatch, capsys):
    patch_fetch(monkeypatch, (payload(five=99.0), ""))
    naps = []
    monkeypatch.setattr(budget.time, "sleep", naps.append)
    ticks = iter([0.0, 10.0, 500.0, 1000.0])
    monkeypatch.setattr(budget.time, "monotonic", lambda: next(ticks))
    assert budget.main(["wait", "--ceiling", "95", "--timeout", "900"]) == 3
    assert "timed out" in capsys.readouterr().err
    assert all(nap >= budget.MIN_POLL for nap in naps)


def test_wait_without_timeout_ignores_the_clock(monkeypatch):
    answers = iter([(payload(five=99.0), ""), (payload(five=1.0), "")])
    patch_fetch(monkeypatch, lambda: next(answers))
    monkeypatch.setattr(budget.time, "sleep", lambda nap: None)
    assert budget.main(["wait"]) == 0


def test_wait_timeout_does_a_final_read(monkeypatch, capsys):
    answers = iter([(payload(five=99.0), ""), (payload(five=10.0), "")])
    patch_fetch(monkeypatch, lambda: next(answers))
    monkeypatch.setattr(budget.time, "sleep", lambda nap: None)
    assert budget.main(["wait", "--timeout", "30"]) == 0
    assert "under 95%" in capsys.readouterr().out


def test_wait_timeout_with_unknown_usage_says_so(monkeypatch, capsys):
    answers = iter([(payload(five=99.0), ""), (None, "down")])
    patch_fetch(monkeypatch, lambda: next(answers))
    monkeypatch.setattr(budget.time, "sleep", lambda nap: None)
    assert budget.main(["wait", "--timeout", "30"]) == 1
    err = capsys.readouterr().err
    assert "usage unknown" in err
    assert "still over" not in err


def test_subcommand_window_is_validated():
    for command in ("show", "check", "wait"):
        with pytest.raises(SystemExit) as raised:
            budget.main([command, "--window", "typo"])
        assert raised.value.code == 2


def test_wait_with_no_matching_window_exits_instead_of_looping(monkeypatch, capsys):
    patch_fetch(monkeypatch, (payload(), ""))
    monkeypatch.setattr(budget.time, "sleep", lambda nap: pytest.fail("looped"))
    assert budget.main(["wait", "--window", "seven_day_opus"]) == 1
    assert "no windows" in capsys.readouterr().err
