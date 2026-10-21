import json
from pathlib import Path
from types import SimpleNamespace

import repo_nav

PY = """import os


class Box:
    def open(self, x: int) -> str:
        return str(x)


def top(a, b=1) -> None:
    pass
"""

MD = "# Title\n\nintro\n\n## One\n\nbody one\n\n### Deep\n\ndeep\n\n## Two\n\nbody two\n"

YML = "version: '3'\ntasks:\n  build:\n    desc: x\n  test:\n    desc: y\n"


def write(tmp_path: Path, name: str, text: str) -> str:
    target = tmp_path / name
    target.write_text(text, encoding="utf-8")
    return str(target)


def test_outline_py(tmp_path: Path, capsys):
    path = write(tmp_path, "a.py", PY)
    assert repo_nav.main(["outline", path]) == 0
    out = capsys.readouterr().out
    assert "4: class Box" in out
    assert "5:   def open(self, x: int) -> str" in out
    assert "9: def top(a, b=1) -> None" in out


def test_outline_depth_one_hides_methods(tmp_path: Path, capsys):
    path = write(tmp_path, "a.py", PY)
    repo_nav.main(["outline", path, "--depth", "1"])
    assert "def open" not in capsys.readouterr().out


def test_outline_md_and_depth(tmp_path: Path, capsys):
    path = write(tmp_path, "a.md", MD)
    repo_nav.main(["outline", path, "--depth", "2"])
    out = capsys.readouterr().out
    assert "5:   One" in out
    assert "Deep" not in out


def test_outline_yaml(tmp_path: Path, capsys):
    path = write(tmp_path, "a.yml", YML)
    repo_nav.main(["outline", path])
    out = capsys.readouterr().out
    assert "2: tasks" in out
    assert "3:   build" in out


def test_outline_other_is_line_count(tmp_path: Path, capsys):
    path = write(tmp_path, "a.txt", "a\nb\n")
    repo_nav.main(["outline", path])
    assert capsys.readouterr().out.strip().endswith("2 lines")


def test_outline_capped(tmp_path: Path, capsys):
    path = write(tmp_path, "big.py", "".join(f"def f{i}(): pass\n" for i in range(100)))
    repo_nav.main(["outline", path])
    assert len(capsys.readouterr().out.splitlines()) <= repo_nav.OUTLINE_MAX


def test_section_py(tmp_path: Path, capsys):
    path = write(tmp_path, "a.py", PY)
    assert repo_nav.main(["section", path, "Box.open"]) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0] == "5:     def open(self, x: int) -> str:"
    assert "top" not in out


def test_section_md(tmp_path: Path, capsys):
    path = write(tmp_path, "a.md", MD)
    assert repo_nav.main(["section", path, "one"]) == 0
    out = capsys.readouterr().out
    assert "5: ## One" in out
    assert "Deep" in out
    assert "Two" not in out


def test_section_missing_and_cap(tmp_path: Path, capsys):
    path = write(tmp_path, "a.md", "# T\n" + "x\n" * 200)
    assert repo_nav.main(["section", path, "nope"]) == 1
    capsys.readouterr()
    repo_nav.main(["section", path, "T"])
    assert len(capsys.readouterr().out.splitlines()) <= repo_nav.SECTION_MAX


def test_tasks_with_grep(monkeypatch, capsys):
    payload = {
        "tasks": [{"name": "a:build", "desc": "Build it"}, {"name": "b:test", "desc": "Run"}]
    }
    calls = []

    def fake(cmd):
        calls.append(cmd)
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(repo_nav, "run", fake)
    assert repo_nav.main(["tasks", "--grep", "build"]) == 0
    assert capsys.readouterr().out.strip() == "a:build - Build it"
    assert calls == [["task", "--list-all", "--json"]]


def test_tasks_failure(monkeypatch, capsys):
    monkeypatch.setattr(
        repo_nav, "run", lambda cmd: SimpleNamespace(returncode=1, stdout="", stderr="boom")
    )
    assert repo_nav.main(["tasks"]) == 1


def test_diff(monkeypatch, capsys):
    stdout = "".join(f"{i}\t1\tf{i}.py\n" for i in range(30)) + "-\t-\timg.png\n"
    seen = []

    def fake(cmd):
        seen.append(cmd)
        return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

    monkeypatch.setattr(repo_nav, "run", fake)
    assert repo_nav.main(["diff", "--base", "main"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert seen == [["git", "diff", "--numstat", "main"]]
    assert len(out) == repo_nav.DIFF_MAX
    assert out[0] == "f0.py +0 -1"


def test_usage_error():
    assert repo_nav.main([]) == 2
