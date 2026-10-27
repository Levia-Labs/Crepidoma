import subprocess

import code_refs


def init(tmp_path, monkeypatch):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    monkeypatch.chdir(tmp_path)


def stage(tmp_path):
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)


def test_lists_source_hits_only_with_total(tmp_path, monkeypatch, capsys):
    init(tmp_path, monkeypatch)
    (tmp_path / "pkg").mkdir()
    long_line = "Foo()  # " + "x" * 200 + "\n"
    (tmp_path / "pkg" / "a.py").write_text("def Foo():\n    pass\n" + long_line, encoding="utf-8")
    (tmp_path / "notes.md").write_text("Foo in docs\n", encoding="utf-8")
    (tmp_path / "other.py").write_text("FooBarBaz = 1\n", encoding="utf-8")
    stage(tmp_path)
    assert code_refs.main(["Foo"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "pkg/a.py:1: def Foo():"
    assert len(lines[1]) == len("pkg/a.py:3: ") + 120
    assert lines[-1] == "total 2"
    assert not any("notes.md" in line or "other.py" in line for line in lines)


def test_path_scope_and_no_match(tmp_path, monkeypatch, capsys):
    init(tmp_path, monkeypatch)
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "a.py").write_text("Foo\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("Foo\n", encoding="utf-8")
    stage(tmp_path)
    assert code_refs.main(["Foo", "pkg"]) == 0
    assert capsys.readouterr().out.splitlines() == ["pkg/a.py:1: Foo", "total 1"]
    assert code_refs.main(["Missing"]) == 0
    assert capsys.readouterr().out.strip() == "total 0"


def test_output_capped_at_forty(tmp_path, monkeypatch, capsys):
    init(tmp_path, monkeypatch)
    (tmp_path / "m.py").write_text("sym\n" * 50, encoding="utf-8")
    stage(tmp_path)
    assert code_refs.main(["sym"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 41
    assert lines[-1] == "total 50 (showing 40)"
