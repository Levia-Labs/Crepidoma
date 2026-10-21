import subprocess
from pathlib import Path

import pin_pillar
import pytest

GIT = [
    "git",
    "-c",
    "user.name=t",
    "-c",
    "user.email=t@example.com",
    "-c",
    "protocol.file.allow=always",
]


def git(cwd: Path, *args: str) -> str:
    done = subprocess.run(
        [*GIT, *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", check=True
    )
    return done.stdout.strip()


@pytest.fixture
def pillar(tmp_path: Path) -> Path:
    """A pillar repo whose .crepidoma submodule sits at v1.0.0, with v1.1.0 upstream."""
    work = tmp_path / "work"
    work.mkdir()
    git(work, "init", "-q", "-b", "main")
    (work / "a.txt").write_text("one", encoding="utf-8")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "one")
    git(work, "tag", "v1.0.0")
    remote = tmp_path / "remote.git"
    git(tmp_path, "clone", "-q", "--bare", str(work), str(remote))
    (work / "a.txt").write_text("two", encoding="utf-8")
    git(work, "commit", "-q", "-am", "two")
    git(work, "tag", "v1.1.0")
    git(work, "push", "-q", str(remote), "main", "--tags")
    root = tmp_path / "demo-pillar"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    git(root, "submodule", "add", "-q", str(remote), ".crepidoma")
    git(root / ".crepidoma", "checkout", "-q", "--detach", "v1.0.0")
    git(root, "add", ".crepidoma")
    git(root, "commit", "-q", "-m", "pin")
    return root


def head(root: Path) -> str:
    return git(root / ".crepidoma", "rev-parse", "HEAD")


def test_valid_tag():
    assert pin_pillar.valid_tag("v1.2.3")
    assert not pin_pillar.valid_tag("1.2.3")
    assert not pin_pillar.valid_tag("v1.2")
    assert not pin_pillar.valid_tag("v1.2.3-rc1")


def test_receipt_formats():
    old, new = "a" * 40, "b" * 40
    assert pin_pillar.receipt("p", ".c", old, "v1.0.0", new) == "p .c aaaaaaa -> v1.0.0 bbbbbbb"
    assert pin_pillar.receipt("p", ".c", old, "v1.0.0", old) == "p already at v1.0.0"


def test_staged_outside_submodule():
    assert pin_pillar.staged_outside(["a.txt", ".crepidoma"], ".crepidoma") == ["a.txt"]
    assert pin_pillar.staged_outside([".crepidoma"], ".crepidoma") == []


def test_happy_path(pillar: Path, capsys):
    old = head(pillar)
    assert pin_pillar.main([str(pillar), "v1.1.0"]) == 0
    new = head(pillar)
    assert new != old
    assert (
        capsys.readouterr().out.strip() == f"demo-pillar .crepidoma {old[:7]} -> v1.1.0 {new[:7]}"
    )
    assert git(pillar, "diff", "--cached", "--name-only") == ".crepidoma"
    assert git(pillar / ".crepidoma", "rev-parse", "v1.1.0^{commit}") == new


def test_already_at_tag(pillar: Path, capsys):
    assert pin_pillar.main([str(pillar), "v1.0.0"]) == 0
    assert capsys.readouterr().out.strip() == "demo-pillar already at v1.0.0"


def test_dirty_submodule_refused(pillar: Path, capsys):
    old = head(pillar)
    (pillar / ".crepidoma" / "a.txt").write_text("dirty", encoding="utf-8")
    assert pin_pillar.main([str(pillar), "v1.1.0"]) == 1
    err = capsys.readouterr().err.strip()
    assert len(err.splitlines()) == 1
    assert head(pillar) == old
    assert (pillar / ".crepidoma" / "a.txt").read_text(encoding="utf-8") == "dirty"


def test_staged_pillar_change_refused(pillar: Path, capsys):
    (pillar / "other.txt").write_text("x", encoding="utf-8")
    git(pillar, "add", "other.txt")
    assert pin_pillar.main([str(pillar), "v1.1.0"]) == 1
    assert "other.txt" in capsys.readouterr().err


def test_bad_tag_refused(pillar: Path, capsys):
    old = head(pillar)
    assert pin_pillar.main([str(pillar), "main"]) == 1
    assert len(capsys.readouterr().err.strip().splitlines()) == 1
    assert head(pillar) == old


def test_unknown_tag_refused(pillar: Path, capsys):
    old = head(pillar)
    assert pin_pillar.main([str(pillar), "v9.9.9"]) == 1
    assert len(capsys.readouterr().err.strip().splitlines()) == 1
    assert head(pillar) == old
