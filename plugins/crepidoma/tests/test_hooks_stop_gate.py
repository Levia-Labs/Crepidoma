"""CREPIDOMA_STOP_GATE=off switches the plugin Stop gate off; any other value keeps it."""

import subprocess

import hooks
import pytest


@pytest.fixture
def calls(monkeypatch, tmp_path):
    marker = tmp_path / "dirty"
    marker.touch()
    gate = hooks.Gate(marker, "", (".py",), ("check",), (), ())
    monkeypatch.setattr(hooks, "GATES", (gate,))
    monkeypatch.setattr(hooks, "opted_in", lambda: True)
    monkeypatch.setattr(hooks, "usage_reading", lambda: {})
    seen = []

    def run(*command):
        seen.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(hooks, "run", run)
    return seen


def test_unset_runs_the_gate(monkeypatch, calls):
    monkeypatch.delenv("CREPIDOMA_STOP_GATE", raising=False)
    assert hooks.stop({}) == 0
    assert calls[0] == ("task", "check")


def test_off_skips_without_running(monkeypatch, calls, capsys):
    monkeypatch.setenv("CREPIDOMA_STOP_GATE", "off")
    assert hooks.stop({}) == 0
    assert calls == []
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("value", ["on", "OFF", "0", "", "false"])
def test_other_values_run_the_gate(monkeypatch, calls, value):
    monkeypatch.setenv("CREPIDOMA_STOP_GATE", value)
    assert hooks.stop({}) == 0
    assert calls[0] == ("task", "check")
