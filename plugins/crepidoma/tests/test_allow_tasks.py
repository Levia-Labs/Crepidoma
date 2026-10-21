import json

import allow_tasks

SUMMARY = {
    "lint:python:check": ["uvx ruff check .", "uvx ruff format --check ."],
    "test:python": ["uv run pytest -q"],
    "claude:lanes": ["python scripts/lanes.py"],
    "claude:allow:*": ["python scripts/allow_tasks.py {{index .MATCH 0}}"],
    "lint:docker:check": ["hadolint Dockerfile"],
    "eval:synthetic:diff": ["python scripts/synth.py diff"],
    "lint:sg:test": ["sg test"],
    "lint:sg:file": ["sg scan --files"],
}

TASKS = list(SUMMARY)


def fake_run(cmd):
    if "--summary" in cmd:
        blocks = []
        for name in cmd[cmd.index("--summary") + 1 :]:
            lines = "\n".join(f" - {c}" for c in SUMMARY.get(name, []))
            blocks.append(f"task: {name}\n\ncommands:\n{lines}\n")
        return "\n".join(blocks)
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


def check(tmp_path, monkeypatch, capsys, allow):
    monkeypatch.setattr(allow_tasks, "run", fake_run)
    allow_tasks.main(["check", "--settings", str(write_settings(tmp_path, allow))])
    return capsys.readouterr().out.splitlines()


def test_wildcard_task_matches_concrete_names(tmp_path, monkeypatch, capsys):
    allow = ["Bash(task claude:allow:check)", "Bash(task claude:allow:report)"]
    assert check(tmp_path, monkeypatch, capsys, allow) == []


def test_wildcard_needs_a_segment_and_prefix():
    names = {"claude:allow:*"}
    assert allow_tasks.task_exists("claude:allow:a:b", names, False)
    assert not allow_tasks.task_exists("claude:allow", names, False)
    assert not allow_tasks.task_exists("claude:other:x", names, False)


def test_unrelated_commands_are_not_bypasses(tmp_path, monkeypatch, capsys):
    allow = [
        "Bash(docker ps *)",
        "Bash(docker compose up *)",
        "Bash(diff *)",
        "Bash(test *)",
        "Bash(file *)",
    ]
    assert check(tmp_path, monkeypatch, capsys, allow) == []


def test_real_bypasses(tmp_path, monkeypatch, capsys):
    out = check(tmp_path, monkeypatch, capsys, ["Bash(ruff *)", "Bash(pytest *)"])
    assert out == [
        "Bash(ruff *): bypasses task lint:python:check",
        "Bash(pytest *): bypasses task test:python",
    ]


def test_interpreter_rules_always_reported(tmp_path, monkeypatch, capsys):
    allow = [f"Bash({c} *)" for c in ("python", "python3", "node", "xargs", "find")]
    allow += ["Bash(sh -c *)", "Bash(bash -c *)"]
    out = check(tmp_path, monkeypatch, capsys, allow)
    assert out == [f"{r}: interpreter or wrapper" for r in allow]


def test_executables_look_through_launchers():
    assert allow_tasks.executables("uv run pytest -q && uvx ruff check .") >= {"pytest", "ruff"}
    assert "test" not in allow_tasks.executables("sg scan --files")
