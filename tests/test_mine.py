import json

import mine


def usage_line(tokens):
    message = {
        "id": "m",
        "model": "claude-sonnet-4",
        "usage": {"input_tokens": tokens, "output_tokens": 0},
        "content": [],
    }
    return json.dumps({"timestamp": "2026-01-01T00:00:00Z", "message": message})


def command_line(command):
    block = {"type": "tool_use", "name": "Bash", "input": {"command": command}}
    return json.dumps({"message": {"content": [block]}})


def make_project(root, slug, tokens, commands):
    folder = root / slug
    folder.mkdir(parents=True)
    lines = [usage_line(tokens), *(command_line(c) for c in commands)]
    (folder / "abcdef123456.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_summarise_counts_tokens_sessions_and_top_command(tmp_path):
    make_project(tmp_path, "p1", 1000, ["git status"] * 3 + ["ls"])
    summary, report = mine.summarise(tmp_path / "p1")
    assert summary.sessions == 1
    assert summary.tokens == 1000
    assert summary.top_command == "git status"
    assert summary.top_count == 3
    assert "git status" in report


def test_summarise_without_commands(tmp_path):
    make_project(tmp_path, "p1", 5, [])
    summary, _ = mine.summarise(tmp_path / "p1")
    assert summary.top_command == "-"


def test_format_row_columns():
    summary = mine.Summary("p", 2, 1500, 0.5, "git status", 3)
    assert mine.format_row(summary) == "p  2  1500  $0.50  git status (3)"


def test_main_ranks_projects_and_writes_reports(tmp_path, capsys):
    root = tmp_path / "projects"
    make_project(root, "small", 10, ["ls"])
    make_project(root, "big", 9000, ["git status"] * 2)
    out = tmp_path / "out"
    assert mine.main(["--root", str(root), "--out", str(out)]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("big  1  9000")
    assert lines[1].startswith("small")
    assert lines[-1] == f"reports {out}"
    assert (out / "big.txt").is_file()
    assert (out / "small.txt").is_file()


def test_main_caps_rows_at_twenty(tmp_path, capsys):
    root = tmp_path / "projects"
    for index in range(25):
        make_project(root, f"p{index:02d}", index + 1, ["ls"])
    assert mine.main(["--root", str(root), "--out", str(tmp_path / "o"), "--top", "99"]) == 0
    assert len(capsys.readouterr().out.splitlines()) == 20


def test_main_missing_root_fails(tmp_path):
    assert mine.main(["--root", str(tmp_path / "none"), "--out", str(tmp_path / "o")]) == 1


def test_main_default_out_is_temp_dir(tmp_path, capsys):
    root = tmp_path / "projects"
    make_project(root, "p", 1, ["ls"])
    assert mine.main(["--root", str(root)]) == 0
    assert capsys.readouterr().out.splitlines()[-1].startswith("reports ")
