import subprocess
from pathlib import Path

import pytest
import ratchet


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    git(tmp_path, "init", "-q")
    (tmp_path / "uv.lock").write_text("x\n" * 50, encoding="utf-8")
    (tmp_path / "sound.ogg").write_bytes(b"ab\0\n" * 50)
    (tmp_path / "latin.dat").write_bytes(b"\xff\xfe\n" * 50)
    (tmp_path / "big.py").write_text("x\n" * 50, encoding="utf-8")
    git(tmp_path, "add", ".")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_only_code_is_reported(repo: Path, capsys: pytest.CaptureFixture[str]):
    assert ratchet.main(["long-files", "--git", "--max-lines", "3", "--baseline", "b"]) == 1
    out = capsys.readouterr().out
    assert "big.py" in out
    assert "uv.lock" not in out
    assert "sound.ogg" not in out
    assert "latin.dat" not in out


def test_stale_baseline_entries_do_not_fail_and_are_dropped(repo: Path):
    base = repo / "b"
    base.write_text("big.py\t50\nuv.lock\t10\nsound.ogg\t10\n", encoding="utf-8")
    args = ["long-files", "--git", "--max-lines", "3", "--baseline", "b"]
    assert ratchet.main(args) == 0
    assert ratchet.main([*args, "--update"]) == 0
    assert base.read_text(encoding="utf-8") == "big.py\t50\n"


def test_ratchet_dir_files_are_skipped(repo: Path, capsys: pytest.CaptureFixture[str]):
    (repo / ".ratchet").mkdir()
    (repo / ".ratchet" / "docs.baseline").write_text("x\n" * 50, encoding="utf-8")
    git(repo, "add", ".")
    assert ratchet.main(["long-files", "--git", "--max-lines", "3", "--baseline", "b"]) == 1
    assert ".ratchet" not in capsys.readouterr().out
