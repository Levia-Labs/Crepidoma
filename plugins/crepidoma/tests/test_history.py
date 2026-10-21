import json
from pathlib import Path

import history


def write_transcript(path: Path, commands: list[str], tool: str = "Bash") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["not json"]
    for command in commands:
        block = {"type": "tool_use", "name": tool, "input": {"command": command}}
        lines.append(json.dumps({"message": {"content": [block]}}))
    lines.append(json.dumps({"message": {"content": "text"}}))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def test_normalise_replaces_paths_numbers_hashes():
    out = history.normalise("pytest  tests/a/b.py -x 42 abcdef1234")
    assert out == "pytest <path> -x <n> <hash>"


def test_commands_counts_normalised(tmp_path, capsys):
    write_transcript(tmp_path / "s" / "a.jsonl", ["ls src/a 1", "ls src/b 2", "ls src/c 3", "pwd"])
    assert history.main(["commands", "--dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out == ["    3  ls <path> <n>"]


def test_commands_min_and_powershell(tmp_path, capsys):
    write_transcript(tmp_path / "a.jsonl", ["git status", "git status"], tool="PowerShell")
    history.main(["commands", "--dir", str(tmp_path), "--min", "2"])
    assert capsys.readouterr().out.strip() == "2  git status"


def test_inline_detects_oneliners_and_heredocs(tmp_path, capsys):
    cmds = [
        'python -c "print(1)"',
        'python -c "print(2)"',
        "python3 - <<'EOF'\nprint(1)\nEOF",
        'node -e "x"',
        "git commit -m \"$(cat <<'EOF'\nmsg\nEOF\n)\"",
        "ls",
    ]
    write_transcript(tmp_path / "a.jsonl", cmds)
    history.main(["inline", "--dir", str(tmp_path)])
    out = capsys.readouterr().out.splitlines()
    assert out[0].strip().startswith('2  python -c "print(<n>)"')
    assert len(out) == 3
    assert not any("git commit" in line for line in out)


def test_top_capped_at_20_lines_and_1kb(tmp_path, capsys):
    write_transcript(tmp_path / "a.jsonl", [f"tool{chr(97 + i)} {'x' * 70}" for i in range(26)] * 3)
    history.main(["commands", "--dir", str(tmp_path), "--top", "50"])
    out = capsys.readouterr().out
    assert len(out.splitlines()) <= 20
    assert len(out.encode()) <= 1024


def test_default_top_is_10(tmp_path, capsys):
    write_transcript(tmp_path / "a.jsonl", [f"tool{chr(97 + i)}" for i in range(15)] * 3)
    history.main(["commands", "--dir", str(tmp_path)])
    assert len(capsys.readouterr().out.splitlines()) == 10


def test_prompts_repeated_across_projects(tmp_path, capsys):
    log = tmp_path / "history.jsonl"
    entries = [
        {"display": "run the tests for 3 files", "project": "p1"},
        {"display": "run the tests for 5 files", "project": "p2"},
        {"display": "x" * 200, "project": "p1"},
        {"display": "x" * 200, "project": "p3"},
        {"display": "unique prompt here", "project": "p1"},
        {"display": "ok", "project": "p1"},
        {"display": "ok", "project": "p1"},
    ]
    log.write_text("\n".join(json.dumps(e) for e in entries) + "\nbad\n", encoding="utf-8")
    assert history.main(["prompts", "--prompts", str(log)]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "    2  run the tests for <n> files"
    assert out[1] == f"    2  {'x' * 80}"
    assert len(out) == 2


def test_missing_sources_exit_1(tmp_path, capsys):
    assert history.main(["commands", "--dir", str(tmp_path / "none")]) == 1
    assert history.main(["prompts", "--prompts", str(tmp_path / "none.jsonl")]) == 1


def test_default_dir_uses_project_slug(tmp_path, monkeypatch):
    monkeypatch.setattr(history.Path, "home", lambda: tmp_path)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", "/a/b c")
    assert history.default_dir() == tmp_path / ".claude" / "projects" / "-a-b-c"


def test_report_writes_all(tmp_path, capsys):
    write_transcript(tmp_path / "a.jsonl", [f"tool{chr(97 + i)}" for i in range(15)] * 3)
    report = tmp_path / "r.txt"
    history.main(["commands", "--dir", str(tmp_path), "--report", str(report)])
    assert len(report.read_text(encoding="utf-8").splitlines()) == 15


def test_usage_error_exits_2():
    try:
        history.main([])
    except SystemExit as exit_:
        assert exit_.code == 2


def test_sessions_lists_transcript_sizes(tmp_path, capsys):
    write_transcript(tmp_path / "a.jsonl", ["ls"])
    write_transcript(tmp_path / "sub" / "b.jsonl", ["ls"])
    assert history.main(["sessions", "--dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out.splitlines()
    assert [line.split()[-1] for line in out] == ["a.jsonl", "b.jsonl"]


def test_untasked_skips_commands_with_a_task(tmp_path, capsys):
    folder = tmp_path / "taskfiles" / "demo"
    folder.mkdir(parents=True)
    (folder / "Taskfile.yml").write_text("tasks:\n  build:\n    desc: x\n", encoding="utf-8")
    write_transcript(tmp_path / "t" / "a.jsonl", ["make all"] * 3 + ["x build"] * 3 + ["ls"] * 3)
    assert history.main(["untasked", "--dir", str(tmp_path / "t"), "--root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "make all" in out
    assert "x build" not in out
    assert "ls" not in out
