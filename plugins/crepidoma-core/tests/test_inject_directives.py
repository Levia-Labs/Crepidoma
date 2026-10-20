import json
from pathlib import Path

import inject_directives as inj


def context(capsys) -> str:
    return json.loads(capsys.readouterr().out)["hookSpecificOutput"]["additionalContext"]


def test_build_orders_and_joins(tmp_path: Path):
    (tmp_path / "20-b.md").write_text("B\n", encoding="utf-8")
    (tmp_path / "10-a.md").write_text("A\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("ignored", encoding="utf-8")
    assert inj.build(tmp_path) == "A\n\nB"


def test_main_emits_session_start_json(tmp_path: Path, monkeypatch, capsys):
    (tmp_path / "10-a.md").write_text("rule one\n", encoding="utf-8")
    monkeypatch.setattr(inj, "DIRECTIVES", tmp_path)
    assert inj.main() == 0
    data = json.loads(capsys.readouterr().out)
    assert data == {
        "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "rule one"}
    }


def test_missing_directory_fails_open(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr(inj, "DIRECTIVES", tmp_path / "absent")
    assert inj.main() == 0
    assert context(capsys).startswith("Crepidoma directives unavailable")


def test_oversize_is_truncated_with_notice(tmp_path: Path, monkeypatch, capsys):
    (tmp_path / "10-a.md").write_text("x" * (inj.LIMIT + 50), encoding="utf-8")
    monkeypatch.setattr(inj, "DIRECTIVES", tmp_path)
    assert inj.main() == 0
    text = context(capsys)
    assert len(text) <= inj.LIMIT
    assert text.endswith(inj.TRUNCATED)


def test_undecodable_directive_fails_open(tmp_path: Path, monkeypatch, capsys):
    (tmp_path / "10-a.md").write_bytes(b"\xff\xfe broken")
    monkeypatch.setattr(inj, "DIRECTIVES", tmp_path)
    assert inj.main() == 0
    assert context(capsys).startswith("Crepidoma directives unavailable")
