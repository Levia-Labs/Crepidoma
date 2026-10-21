import json
import time

import hooks
import hooks_pre_tool
import lanes
import pytest
from hooks_patch import patch_shared


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    path = tmp_path / "claude-lanes.json"
    monkeypatch.setattr(hooks_pre_tool, "LEDGER", path)
    patch_shared(monkeypatch, "ROOT", tmp_path)

    def write(running: dict, pending: dict) -> None:
        path.write_text(json.dumps({"running": running, "pending": pending}), encoding="utf-8")

    return write


def test_list_shows_lanes_and_cap(ledger, capsys):
    now = time.time()
    ledger({"agent-a": now - 120}, {"tool-b": now - 5})
    assert lanes.main(["list"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith("agent-a - ") and out[0].endswith("running")
    assert out[1].startswith("tool-b - ") and out[1].endswith("pending")
    assert out[-1] == f"1 running, 1 pending, cap {hooks.MAX_AGENTS}"


def test_list_empty(ledger, capsys):
    assert lanes.main(["list"]) == 0
    assert capsys.readouterr().out.strip() == f"0 running, 0 pending, cap {hooks.MAX_AGENTS}"


def test_reset_clears_all(ledger, capsys):
    now = time.time()
    ledger({"a": now, "b": now - hooks.RUNNING_SECONDS - 10}, {"c": now})
    assert lanes.main(["reset"]) == 0
    assert capsys.readouterr().out.strip() == "removed 3"
    state = json.loads(hooks_pre_tool.LEDGER.read_text(encoding="utf-8"))
    assert state == {"running": {}, "pending": {}}


def test_reset_stale_keeps_fresh(ledger, capsys):
    now = time.time()
    ledger({"a": now, "b": now - hooks.RUNNING_SECONDS - 10}, {})
    assert lanes.main(["reset", "--stale"]) == 0
    assert capsys.readouterr().out.strip() == "removed 1"
    state = json.loads(hooks_pre_tool.LEDGER.read_text(encoding="utf-8"))
    assert list(state["running"]) == ["a"]


def test_handoff_writes_note(ledger, tmp_path, monkeypatch, capsys):
    ledger({"a": time.time()}, {})
    (tmp_path / "TODO.md").write_text("- TODO one\n- done\n- TODO two\n", encoding="utf-8")
    replies = {
        "rev-parse": "foundation\n",
        "log": "abc one\ndef two\n",
        "status": " M file.py\n?? new.md\n?? other.md\n",
    }
    monkeypatch.setattr(lanes, "git", lambda *args: replies[args[0]])
    assert lanes.main(["handoff"]) == 0
    note = tmp_path / ".claude" / "handoff.md"
    text = note.read_text(encoding="utf-8")
    assert "branch: foundation" in text
    assert "status: 1 changed, 2 untracked" in text
    assert "running lanes: 1" in text
    assert "open TODO markers: 2" in text
    assert "- abc one" in text
    assert capsys.readouterr().out.strip() == f"{note} {len(text.splitlines())} lines"


def test_handoff_custom_out_without_todo(ledger, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(lanes, "git", lambda *args: "")
    assert lanes.main(["handoff", "--out", "notes/x.md"]) == 0
    assert "branch: unknown" in (tmp_path / "notes" / "x.md").read_text(encoding="utf-8")
    assert "open TODO markers: 0" in (tmp_path / "notes" / "x.md").read_text(encoding="utf-8")
    capsys.readouterr()


def test_usage_error_exits_2(capsys):
    assert lanes.main(["bogus"]) == 2
    capsys.readouterr()
