import subprocess

import edit_file
import pytest


@pytest.fixture(autouse=True)
def repo(tmp_path, monkeypatch):
    """Tools only write inside the git work tree of the working directory."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    monkeypatch.chdir(tmp_path)


def run(args):
    return edit_file.main([str(a) for a in args])


def test_replace_once_reports_line_count(tmp_path, capsys):
    target = tmp_path / "a.txt"
    target.write_text("one\ntwo\n", encoding="utf-8", newline="")
    assert run(["replace", target, "--old", "two", "--new", "2"]) == 0
    assert target.read_text(encoding="utf-8") == "one\n2\n"
    assert "1 replacement(s), 2 lines" in capsys.readouterr().out


@pytest.mark.parametrize("old", ["y", "x"])
def test_wrong_count_fails_and_leaves_file(tmp_path, old):
    target = tmp_path / "a.txt"
    target.write_text("x x\n", encoding="utf-8", newline="")
    assert run(["replace", target, "--old", old, "--new", "z"]) == 1
    assert target.read_text(encoding="utf-8") == "x x\n"


def test_count_n_replaces_all(tmp_path):
    target = tmp_path / "a.txt"
    target.write_text("x x\n", encoding="utf-8", newline="")
    assert run(["replace", target, "--old", "x", "--new", "y", "--count", "2"]) == 0
    assert target.read_text(encoding="utf-8") == "y y\n"


def test_crlf_file_keeps_crlf_with_multiline_args(tmp_path):
    target = tmp_path / "a.txt"
    target.write_bytes(b"a\r\nb\r\nc\r\n")
    assert run(["replace", target, "--old", "a\nb", "--new", "x\ny\nz"]) == 0
    assert target.read_bytes() == b"x\r\ny\r\nz\r\nc\r\n"


def test_file_variants(tmp_path):
    target = tmp_path / "a.txt"
    old, new = tmp_path / "old", tmp_path / "new"
    target.write_text("a\nb\nc\n", encoding="utf-8", newline="")
    old.write_text("a\nb\n", encoding="utf-8", newline="")
    new.write_text("Q\n", encoding="utf-8", newline="")
    assert run(["replace", target, "--old-file", old, "--new-file", new]) == 0
    assert target.read_text(encoding="utf-8") == "Q\nc\n"


def test_insert_after_anchor(tmp_path, capsys):
    target = tmp_path / "a.txt"
    target.write_text("head\nbody\n", encoding="utf-8", newline="")
    assert run(["insert-after", target, "--anchor", "head\n", "--text", "mid\n"]) == 0
    assert target.read_text(encoding="utf-8") == "head\nmid\nbody\n"
    assert "3 lines" in capsys.readouterr().out


def test_insert_after_ambiguous_anchor_fails(tmp_path):
    target = tmp_path / "a.txt"
    target.write_text("k\nk\n", encoding="utf-8", newline="")
    assert run(["insert-after", target, "--anchor", "k", "--text", "!"]) == 1


def test_missing_file_and_empty_old(tmp_path):
    assert run(["replace", tmp_path / "none", "--old", "a", "--new", "b"]) == 1
    target = tmp_path / "a.txt"
    target.write_text("a", encoding="utf-8")
    assert run(["replace", target, "--old", "", "--new", "b"]) == 1


@pytest.mark.parametrize(
    "name",
    [
        ".git/config",
        ".claude/x.txt",
        "settings.json",
        "sub/settings.local.json",
        "hooks.json",
        ".pre-commit-config.yaml",
    ],
)
def test_protected_targets_refused(tmp_path, name):
    target = tmp_path / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("a\n", encoding="utf-8", newline="")
    assert run(["replace", target, "--old", "a", "--new", "b"]) == 1
    assert target.read_text(encoding="utf-8") == "a\n"


def test_target_outside_repo_refused(tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside") / "a.txt"
    outside.write_text("a\n", encoding="utf-8", newline="")
    assert run(["replace", outside, "--old", "a", "--new", "b"]) == 1
    assert outside.read_text(encoding="utf-8") == "a\n"


def test_input_files_outside_repo_refused(tmp_path, tmp_path_factory):
    target = tmp_path / "a.txt"
    target.write_text("a\n", encoding="utf-8", newline="")
    secret = tmp_path_factory.mktemp("outside") / "s.txt"
    secret.write_text("a", encoding="utf-8")
    assert run(["replace", target, "--old-file", secret, "--new", "b"]) == 1
    assert run(["replace", target, "--old", "a", "--new-file", secret]) == 1
    assert run(["insert-after", target, "--anchor", "a", "--text-file", secret]) == 1
    assert target.read_text(encoding="utf-8") == "a\n"


def test_input_file_in_protected_place_refused(tmp_path):
    target = tmp_path / "a.txt"
    target.write_text("a\n", encoding="utf-8", newline="")
    (tmp_path / ".claude").mkdir()
    text = tmp_path / ".claude" / "t.txt"
    text.write_text("b", encoding="utf-8")
    assert run(["replace", target, "--old", "a", "--new-file", text]) == 1
