"""Tests for todo.py: list, show, add, set and drop over a TODO.md in tmp_path."""

import todo

SEED = (
    "# TODO\n\nIntro text.\n\n"
    "## 1 First\nstatus: open\nclass: fixable\n\nBody one.\n\n"
    "## 2 Second\nstatus: done\nclass: stale\n"
)


def run(path, *args):
    return todo.main([*args, "--file", str(path)])


def seeded(tmp_path):
    path = tmp_path / "TODO.md"
    path.write_text(SEED, encoding="utf-8", newline="\n")
    return path


def test_list_all_and_filters(tmp_path, capsys):
    path = seeded(tmp_path)
    assert run(path, "list") == 0
    assert capsys.readouterr().out.splitlines() == ["1 open fixable First", "2 done stale Second"]
    assert run(path, "list", "--status", "done") == 0
    assert capsys.readouterr().out.splitlines() == ["2 done stale Second"]
    assert run(path, "list", "--class", "fixable") == 0
    assert capsys.readouterr().out.splitlines() == ["1 open fixable First"]


def test_list_limit(tmp_path, capsys):
    path = seeded(tmp_path)
    assert run(path, "list", "--limit", "1") == 0
    assert capsys.readouterr().out.splitlines() == ["1 open fixable First", "... 1 more"]


def test_show(tmp_path, capsys):
    path = seeded(tmp_path)
    assert run(path, "show", "1") == 0
    out = capsys.readouterr().out
    assert "## 1 First" in out and "Body one." in out and "Second" not in out
    assert run(path, "show", "9") == 1


def test_add_creates_file_and_increments(tmp_path, capsys):
    path = tmp_path / "TODO.md"
    assert run(path, "add", "--title", "A", "--class", "fixable", "--body", "why") == 0
    assert capsys.readouterr().out.strip() == "1"
    assert run(path, "add", "--title", "B", "--class", "stale") == 0
    assert capsys.readouterr().out.strip() == "2"
    text = path.read_text(encoding="utf-8")
    assert "## 1 A\n\nstatus: open\nclass: fixable\n\nwhy\n" in text
    assert "## 2 B\n\nstatus: open\nclass: stale\n" in text
    assert "\r" not in text


def test_add_after_seed_uses_next_id(tmp_path, capsys):
    path = seeded(tmp_path)
    assert run(path, "add", "--title", "Third", "--class", "record") == 0
    assert capsys.readouterr().out.strip() == "3"
    assert path.read_text(encoding="utf-8").startswith("# TODO\n\nIntro text.\n")


def test_add_rejects_bad_input(tmp_path, capsys):
    path = tmp_path / "TODO.md"
    assert run(path, "add", "--title", "x", "--class", "two words") == 2
    assert run(path, "add", "--title", "x", "--class", "c", "--body", "## 5 sneaky") == 2
    assert not path.exists()


def test_set_status(tmp_path, capsys):
    path = seeded(tmp_path)
    assert run(path, "set", "1", "--status", "done") == 0
    assert capsys.readouterr().out.strip() == "1 status done"
    assert "## 1 First\n\nstatus: done\nclass: fixable\n\nBody one." in path.read_text(
        encoding="utf-8"
    )
    assert run(path, "set", "9", "--status", "done") == 1


def test_drop(tmp_path, capsys):
    path = seeded(tmp_path)
    assert run(path, "drop", "1") == 0
    text = path.read_text(encoding="utf-8")
    assert "First" not in text and "Body one." not in text and "## 2 Second" in text
    assert "Intro text." in text
    assert run(path, "drop", "1") == 1


def test_missing_file_and_usage(tmp_path, capsys):
    assert run(tmp_path / "none.md", "list") == 1
    assert todo.main([]) == 2


def test_default_file_uses_project_dir(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    assert todo.main(["add", "--title", "T", "--class", "fixable"]) == 0
    assert (tmp_path / "TODO.md").exists()


def test_add_output_matches_prettier_format(tmp_path):
    path = tmp_path / "TODO.md"
    assert run(path, "add", "--title", "T", "--class", "bug", "--body", "text") == 0
    assert path.read_text(encoding="utf-8") == (
        "# TODO\n\n## 1 T\n\nstatus: open\nclass: bug\n\ntext\n"
    )
    assert run(path, "set", "1", "--status", "done") == 0
    assert run(path, "add", "--title", "U", "--class", "bug") == 0
    assert path.read_text(encoding="utf-8") == (
        "# TODO\n\n## 1 T\n\nstatus: done\nclass: bug\n\ntext\n\n"
        "## 2 U\n\nstatus: open\nclass: bug\n"
    )
