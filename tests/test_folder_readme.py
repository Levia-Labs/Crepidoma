from pathlib import Path

import folder_readme as fr

BS = chr(92)  # a Windows path separator, spelled so no layer eats the escape


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


def test_path_key_beats_basename_and_accepts_windows_separators(tmp_path: Path):
    make(tmp_path, "a/entity_test.go", "")
    make(tmp_path, "b/entity_test.go", "")
    overrides = {"a" + BS + "entity_test.go": "A tests.", "entity_test.go": "Generic tests."}
    a_path, b_path = "a/entity_test.go", "b/entity_test.go"
    assert fr.describe(tmp_path / a_path, overrides, a_path) == "A tests."
    assert fr.describe(tmp_path / b_path, overrides, b_path) == "Generic tests."
    toml = '[files]\n"a' + BS * 2 + 'entity_test.go" = "X."\n'
    purposes, _ = fr.load_purposes(make(tmp_path, "p.toml", toml))
    assert purposes["files"] == {a_path: "X."}
    listing = fr.contents(tmp_path, "a", [a_path, b_path], purposes, set())
    assert "- [`entity_test.go`](entity_test.go) - X." in listing


def test_include_merges_and_duplicate_names_both_files(tmp_path: Path):
    make(tmp_path, "docs/main.toml", 'include = ["main.d/*.toml"]\n[folders]\n"a" = "A."\n')
    make(tmp_path, "docs/main.d/x.toml", '[folders]\n"b" = "B."\n[files]\n"a/f.py" = "F."\n')
    purposes, _ = fr.load_purposes(tmp_path / "docs/main.toml")
    assert purposes == {"folders": {"a": "A.", "b": "B."}, "files": {"a/f.py": "F."}}
    dup = make(tmp_path, "docs/main.d/y.toml", '[folders]\n"a" = "Again."\n')
    try:
        fr.load_purposes(tmp_path / "docs/main.toml")
    except SystemExit as err:
        assert "main.toml" in str(err) and str(dup) in str(err)
    else:
        raise AssertionError("duplicate key accepted")


def test_add_sorts_refuses_duplicate_and_replaces(tmp_path: Path):
    files = setup(tmp_path)
    main = make(tmp_path, "p.toml", '# note\n[folders]\n"tasks" = "T."\n"tools/sub" = "S."\n')
    assert fr.add(tmp_path, files, main, "tools", "Tools.", False) == "folders"
    lines = main.read_text(encoding="utf-8").splitlines()
    assert lines[2:5] == ['"tasks" = "T."', '"tools" = "Tools."', '"tools/sub" = "S."']
    assert fr.add(tmp_path, files, main, "tools" + BS + "run.py", "Runner.", False) == "files"
    assert '"tools/run.py" = "Runner."' in main.read_text(encoding="utf-8")
    try:
        fr.add(tmp_path, files, main, "tools", "Again.", False)
    except SystemExit as err:
        assert "--replace" in str(err)
    else:
        raise AssertionError("duplicate accepted")
    fr.add(tmp_path, files, main, "tools", "New.", True)
    assert '"tools" = "New."' in main.read_text(encoding="utf-8")
    assert "# note" in main.read_text(encoding="utf-8")
