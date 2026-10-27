import subprocess

import pytest
import sdd_ledger


@pytest.fixture(autouse=True)
def repo(tmp_path, monkeypatch):
    """Tools only write inside the git work tree of the working directory."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    monkeypatch.chdir(tmp_path)


REVIEW = """\
High | a.py:1 | bad thing | do it
Low | b.py:2 | nit one | fix one
- Minor | c.py:3 | nit two | fix | two
prose line
"""


def test_progress_creates_ledger_with_title(tmp_path):
    ledger = tmp_path / "ledger.md"
    assert sdd_ledger.main(["progress", str(ledger), "task 1 done"]) == 0
    assert sdd_ledger.main(["progress", str(ledger), "task 2 done"]) == 0
    assert ledger.read_text(encoding="utf-8") == "# ledger\n\ntask 1 done\ntask 2 done\n"


def test_progress_refuses_multiline_and_empty(tmp_path):
    ledger = tmp_path / "ledger.md"
    assert sdd_ledger.main(["progress", str(ledger), "a\nb"]) == 2
    assert sdd_ledger.main(["progress", str(ledger), "  "]) == 2
    assert not ledger.exists()


def test_findings_keep_only_low_and_minor():
    assert sdd_ledger.findings(REVIEW) == [
        ("b.py:2", "nit one", "fix one"),
        ("c.py:3", "nit two", "fix | two"),
    ]


def test_defer_adds_debt_entries(tmp_path, capsys):
    review, todo = tmp_path / "review.txt", tmp_path / "TODO.md"
    review.write_text(REVIEW, encoding="utf-8")
    assert sdd_ledger.main(["defer", str(review), "--todo-file", str(todo)]) == 0
    assert capsys.readouterr().out.strip() == "deferred 2: 1 2"
    text = todo.read_text(encoding="utf-8")
    assert "class: debt" in text and "b.py:2 nit one" in text


def test_defer_without_findings(tmp_path, capsys):
    review = tmp_path / "review.txt"
    review.write_text("High | a:1 | x | y\n", encoding="utf-8")
    assert sdd_ledger.main(["defer", str(review), "--todo-file", str(tmp_path / "T.md")]) == 0
    assert capsys.readouterr().out.strip() == "deferred 0"


@pytest.mark.parametrize("name", [".git/L.md", ".claude/L.md"])
def test_progress_refuses_protected_ledger(tmp_path, name):
    (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
    assert sdd_ledger.main(["progress", str(tmp_path / name), "x"]) == 1
    assert not (tmp_path / name).exists()


def test_progress_refuses_ledger_outside_repo(tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside") / "L.md"
    assert sdd_ledger.main(["progress", str(outside), "x"]) == 1
    assert not outside.exists()


def test_defer_refuses_todo_file_outside_repo_or_protected(tmp_path, tmp_path_factory):
    review = tmp_path / "review.txt"
    review.write_text(REVIEW, encoding="utf-8")
    outside = tmp_path_factory.mktemp("outside") / "T.md"
    assert sdd_ledger.main(["defer", str(review), "--todo-file", str(outside)]) == 1
    (tmp_path / ".claude").mkdir()
    inside = tmp_path / ".claude" / "T.md"
    assert sdd_ledger.main(["defer", str(review), "--todo-file", str(inside)]) == 1
    assert not outside.exists() and not inside.exists()
