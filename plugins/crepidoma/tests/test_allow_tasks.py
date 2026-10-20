import json

import allow_tasks

TASKS = ["lint:python:check", "test:python", "claude:lanes"]


def fake_run(cmd):
    return json.dumps({"tasks": [{"name": n} for n in TASKS]})


def write_settings(tmp_path, allow, deny=()):
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps({"permissions": {"allow": allow, "deny": list(deny)}}), encoding="utf-8"
    )
    return path


def test_check_clean(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(allow_tasks, "run", fake_run)
    path = write_settings(tmp_path, ["Bash(task *)", "Bash(task claude:*)", "Bash(git status)"])
    assert allow_tasks.main(["check", "--settings", str(path)]) == 0
    assert capsys.readouterr().out == ""


def test_check_findings(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(allow_tasks, "run", fake_run)
    path = write_settings(
        tmp_path,
        ["Bash(ruff *)", "Bash(task foo:*)", "Bash(task test:python)", "PowerShell(Get-Date)"],
    )
    assert allow_tasks.main(["check", "--settings", str(path)]) == 1
    lines = capsys.readouterr().out.splitlines()
    assert lines == [
        "Bash(ruff *): bypasses task lint:python:check",
        "Bash(task foo:*): task foo does not exist",
        "PowerShell(Get-Date): PowerShell must be denied, not allowed",
    ]


def test_report(tmp_path, capsys):
    path = write_settings(
        tmp_path, ["Bash(a)", "Bash(b)", "Read(x)"], deny=["PowerShell", "Bash(c)"]
    )
    assert allow_tasks.main(["report", "--settings", str(path)]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "allow Bash: 2",
        "allow Read: 1",
        "deny Bash: 1",
        "deny PowerShell: 1",
    ]


def test_missing_settings(tmp_path, capsys):
    assert allow_tasks.main(["report", "--settings", str(tmp_path / "none.json")]) == 2


def test_namespace_segment_alone_is_not_a_bypass():
    names = {"git:commit", "git:status", "lint:python:check"}
    assert allow_tasks.bypassed_task("git status --short", names) is None
    assert allow_tasks.bypassed_task("ruff check .", names) == "lint:python:check"
