from pathlib import Path

import denylist


def test_parse_slug():
    assert denylist.parse_slug("https://github.com/Org/Repo.git\n") == "Org/Repo"
    assert denylist.parse_slug("git" + "@" + "github.com:Org/Repo.git") == "Org/Repo"
    assert denylist.parse_slug("https://gitlab.com/x/y") is None


def test_collect_private_and_remote_less(tmp_path: Path):
    for name in ("alpha", "beta"):
        (tmp_path / name / ".git").mkdir(parents=True)
    (tmp_path / "gamma" / "app").mkdir(parents=True)
    (tmp_path / "gamma" / "app" / "package.json").write_text("{}", encoding="utf-8")
    (tmp_path / "file.txt").write_text("x", encoding="utf-8")
    remotes = {"alpha": "Org/alpha-repo", "beta": "Org/beta", "gamma": None}
    private = {"Org/alpha-repo": True, "Org/beta": False}
    names = denylist.collect(
        tmp_path, remote=lambda d: remotes[d.name], probe=lambda slug: private[slug]
    )
    assert names == ["alpha", "alpha-repo", "gamma"]


def test_main_writes_lf_file(tmp_path: Path, monkeypatch):
    (tmp_path / "pillars" / "secret").mkdir(parents=True)
    (tmp_path / "pillars" / "secret" / "pyproject.toml").write_text("", encoding="utf-8")
    out = tmp_path / "deny"
    monkeypatch.setattr(denylist, "remote_slug", lambda d: None)
    assert denylist.main([str(tmp_path / "pillars"), "--out", str(out)]) == 0
    raw = out.read_bytes()
    assert b"\r\n" not in raw
    lines = raw.decode("utf-8").splitlines()
    assert lines[0].startswith("#")
    assert lines[1:] == ["secret"]


def test_collect_skips_directories_that_are_not_repos(tmp_path: Path):
    (tmp_path / "repo" / ".git").mkdir(parents=True)
    (tmp_path / "docs").mkdir()
    names = denylist.collect(tmp_path, remote=lambda d: None, probe=lambda slug: True)
    assert names == ["repo"]
