from pathlib import Path

import folder_readme as fr


def make(root: Path, rel: str, text: str = "") -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def setup(tmp_path: Path) -> list[str]:
    make(tmp_path, "tools/run.py", '"""Run the thing.\n\nUsage: run.py\n"""\n')
    make(tmp_path, "tools/sub/note.md", "---\ndescription: A note for agents.\n---\nbody\n")
    make(tmp_path, "tools/data.json", "{}")
    make(tmp_path, "tasks/Taskfile.yml", "tasks:\n  a:\n    desc: A\n  b:\n    desc: B\n")
    return ["tools/run.py", "tools/sub/note.md", "tools/data.json", "tasks/Taskfile.yml"]


def test_describe_extracts_from_each_kind(tmp_path: Path):
    setup(tmp_path)
    assert fr.describe(tmp_path / "tools/run.py", {}) == "Run the thing."
    assert fr.describe(tmp_path / "tools/sub/note.md", {}) == "A note for agents."
    assert fr.describe(tmp_path / "tasks/Taskfile.yml", {}) == "Task namespace with 2 tasks."
    assert fr.describe(tmp_path / "tools/data.json", {}) == "JSON data or config."


def test_update_creates_readmes_with_contents_block(tmp_path: Path):
    files = setup(tmp_path)
    purposes = {"folders": {"tools": "Helper scripts."}}
    changed = fr.update(tmp_path, files, purposes, excluded=set())
    assert set(changed) == {"tools", "tools/sub", "tasks"}
    text = (tmp_path / "tools/README.md").read_text(encoding="utf-8")
    assert text.startswith("# Tools\n\n- Helper scripts.\n")
    assert "- [`run.py`](run.py) - Run the thing." in text
    assert "- [`sub/`](sub/README.md) - " in text
    assert fr.MARK_START in text and fr.MARK_END in text


def test_update_keeps_hand_text_and_refreshes_block(tmp_path: Path):
    files = setup(tmp_path)
    fr.update(tmp_path, files, {}, excluded=set())
    readme = tmp_path / "tools/README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8").replace("# Tools", "# Tools\n\nHand note."),
        encoding="utf-8",
    )
    make(tmp_path, "tools/new.py", '"""New tool."""\n')
    fr.update(tmp_path, [*files, "tools/new.py"], {}, excluded=set())
    text = readme.read_text(encoding="utf-8")
    assert "Hand note." in text
    assert "[`new.py`](new.py) - New tool." in text


def test_readme_without_markers_is_left_alone(tmp_path: Path):
    files = setup(tmp_path)
    make(tmp_path, "tools/README.md", "# Custom\n")
    fr.update(tmp_path, [*files, "tools/README.md"], {}, excluded=set())
    assert (tmp_path / "tools/README.md").read_text(encoding="utf-8") == "# Custom\n"


def test_check_reports_missing_and_stale(tmp_path: Path, capsys):
    files = setup(tmp_path)
    assert fr.check(tmp_path, files, {}, excluded=set()) == 1
    fr.update(tmp_path, files, {}, excluded=set())
    assert fr.check(tmp_path, files, {}, excluded={"tasks"}) == 0
    make(tmp_path, "tools/later.py", '"""Later."""\n')
    assert fr.check(tmp_path, [*files, "tools/later.py"], {}, excluded=set()) == 1
    assert "tools" in capsys.readouterr().out


def test_excluded_folders_get_no_readme(tmp_path: Path):
    files = setup(tmp_path)
    fr.update(tmp_path, files, {}, excluded={"tasks"})
    assert not (tmp_path / "tasks/README.md").exists()


def test_written_files_use_lf(tmp_path: Path):
    files = setup(tmp_path)
    fr.update(tmp_path, files, {}, excluded=set())
    assert b"\r\n" not in (tmp_path / "tools/README.md").read_bytes()


def test_github_folder_never_gets_a_readme():
    # GitHub shows .github/README.md on the repo home page instead of the root README.
    assert ".github" in fr.EXCLUDED
