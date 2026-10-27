import subprocess
from pathlib import Path

import review_files

GIT = [
    "git",
    "-c",
    "user.name=t",
    "-c",
    "user.email=tester",
    "-c",
    "commit.gpgsign=false",
]


def git(cwd, *args):
    subprocess.run([*GIT, *args], cwd=cwd, check=True, capture_output=True)


def test_diff_writes_file_and_prints_path_and_count(tmp_path, monkeypatch, capsys):
    git(tmp_path, "init", "-q")
    (tmp_path / "a.txt").write_text("1\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("1\n", encoding="utf-8")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "base")
    (tmp_path / "a.txt").write_text("2\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("2\n", encoding="utf-8")
    git(tmp_path, "commit", "-qam", "change")
    monkeypatch.chdir(tmp_path)
    assert review_files.main(["diff", "HEAD~1", "HEAD", "a.txt"]) == 0
    out = capsys.readouterr().out.strip()
    assert len(out.splitlines()) == 1
    path, count, _ = out.rsplit(" ", 2)
    text = Path(path).read_text(encoding="utf-8")
    Path(path).unlink()
    assert "change" in text and "a.txt" in text and "b.txt" not in text
    assert int(count) == len(text.splitlines())


def test_diff_bad_range_fails(tmp_path, monkeypatch):
    git(tmp_path, "init", "-q")
    monkeypatch.chdir(tmp_path)
    assert review_files.main(["diff", "nope", "HEAD"]) == 1


def test_relay_numbers_findings_and_appends_gate(tmp_path, capsys):
    review = tmp_path / "r.txt"
    review.write_text(
        "High | a.py:1 | bug | fix it\nprose\nLow | b.py:2 | nit | tidy\n", encoding="utf-8"
    )
    assert review_files.main(["relay", str(review), "--gate", "task check"]) == 0
    path = Path(capsys.readouterr().out.rsplit(" ", 2)[0])
    lines = path.read_text(encoding="utf-8").splitlines()
    path.unlink()
    assert lines == [
        "1. a.py:1 | bug | fix: fix it",
        "2. b.py:2 | nit | fix: tidy",
        "Gate: task check",
    ]


def test_relay_without_findings_fails(tmp_path):
    review = tmp_path / "r.txt"
    review.write_text("nothing\n", encoding="utf-8")
    assert review_files.main(["relay", str(review)]) == 1


def test_option_like_base_head_or_path_refused(tmp_path, monkeypatch):
    git(tmp_path, "init", "-q")
    (tmp_path / "a.txt").write_text("1\n", encoding="utf-8")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "base")
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "pwned"
    assert review_files.main(["diff", f"--output={out}", "HEAD"]) == 1
    assert review_files.main(["diff", "HEAD", f"--output={out}"]) == 1
    assert review_files.main(["diff", "HEAD", "HEAD", f"--output={out}"]) == 1
    assert not out.exists()
