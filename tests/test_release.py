import json
import subprocess
from pathlib import Path

import release


def setup_repo(root: Path) -> Path:
    manifest = root / "plugins/crepidoma/.claude-plugin/plugin.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"name": "crepidoma", "version": "0.1.0"}), encoding="utf-8")
    (root / "CHANGELOG.md").write_text("# Changelog\n\n## v0.1.0 - 2026-10-20\n", encoding="utf-8")
    return manifest


def test_bump_updates_manifest_and_changelog(tmp_path: Path):
    manifest = setup_repo(tmp_path)
    changed = release.bump(tmp_path, "0.2.0", "2026-11-01")
    assert json.loads(manifest.read_text(encoding="utf-8"))["version"] == "0.2.0"
    changelog = (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8")
    assert changelog.startswith("# Changelog\n\n## v0.2.0 - 2026-11-01\n")
    assert "## v0.1.0" in changelog
    assert len(changed) == 2
    assert b"\r\n" not in manifest.read_bytes()


def test_main_rejects_non_semver():
    assert release.main(["v1"]) == 2


def test_main_dry_run_touches_nothing(tmp_path: Path, monkeypatch):
    manifest = setup_repo(tmp_path)
    monkeypatch.setattr(release, "ROOT", tmp_path)
    assert release.main(["0.3.0", "--dry-run"]) == 0
    assert json.loads(manifest.read_text(encoding="utf-8"))["version"] == "0.1.0"


def test_bump_on_empty_changelog_ends_with_one_newline(tmp_path: Path):
    setup_repo(tmp_path)
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
    release.bump(tmp_path, "0.1.0", "2026-10-20")
    text = (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8")
    assert text == "# Changelog\n\n## v0.1.0 - 2026-10-20\n"


def run_git(cwd: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(cwd), *args], capture_output=True, text=True, encoding="utf-8", check=True
    )
    return done.stdout.strip()


def make_clone(tmp_path: Path) -> Path:
    bare = tmp_path / "origin.git"
    subprocess.run(
        ["git", "init", "--bare", "-b", "main", str(bare)], check=True, capture_output=True
    )
    work = tmp_path / "work"
    work.mkdir()
    run_git(work, "init", "-b", "main")
    for key, value in (("user.name", "t"), ("user.email", "t@example.com")):
        run_git(work, "config", key, value)
    setup_repo(work)
    run_git(work, "add", ".")
    run_git(work, "commit", "-m", "init")
    run_git(work, "remote", "add", "origin", str(bare))
    run_git(work, "push", "origin", "main")
    return work


def attempt(work: Path, monkeypatch, capsys, version: str = "0.3.0"):
    monkeypatch.setattr(release, "ROOT", work)
    head = run_git(work, "rev-parse", "HEAD")
    code = release.main([version])
    assert run_git(work, "rev-parse", "HEAD") == head or code == 0
    return code, capsys.readouterr().err


def test_release_happy_path(tmp_path: Path, monkeypatch, capsys):
    work = make_clone(tmp_path)
    code, err = attempt(work, monkeypatch, capsys)
    assert code == 0 and err == ""
    assert run_git(work, "tag", "--list", "v0.3.0") == "v0.3.0"
    assert run_git(work, "log", "-1", "--format=%s") == "chore(release): v0.3.0"


def test_refuses_off_main(tmp_path: Path, monkeypatch, capsys):
    work = make_clone(tmp_path)
    run_git(work, "checkout", "-b", "feature")
    code, err = attempt(work, monkeypatch, capsys)
    assert code == 1 and err.count(chr(10)) == 1 and "feature" in err
    assert run_git(work, "tag", "--list") == ""


def test_refuses_dirty_tree(tmp_path: Path, monkeypatch, capsys):
    work = make_clone(tmp_path)
    (work / "CHANGELOG.md").write_text("edited", encoding="utf-8")
    code, err = attempt(work, monkeypatch, capsys)
    assert code == 1 and err.count(chr(10)) == 1 and "tracked changes" in err


def test_refuses_when_main_differs_from_origin(tmp_path: Path, monkeypatch, capsys):
    work = make_clone(tmp_path)
    run_git(work, "commit", "--allow-empty", "-m", "local only")
    code, err = attempt(work, monkeypatch, capsys)
    assert code == 1 and err.count(chr(10)) == 1 and "origin" in err


def test_refuses_existing_local_tag(tmp_path: Path, monkeypatch, capsys):
    work = make_clone(tmp_path)
    run_git(work, "tag", "v0.3.0")
    code, err = attempt(work, monkeypatch, capsys)
    assert code == 1 and err.count(chr(10)) == 1 and "already exists" in err


def test_refuses_existing_remote_tag(tmp_path: Path, monkeypatch, capsys):
    work = make_clone(tmp_path)
    run_git(work, "tag", "v0.3.0")
    run_git(work, "push", "origin", "v0.3.0")
    run_git(work, "tag", "-d", "v0.3.0")
    code, err = attempt(work, monkeypatch, capsys)
    assert code == 1 and err.count(chr(10)) == 1 and "already exists" in err


def test_refuses_version_not_greater_than_latest_tag(tmp_path: Path, monkeypatch, capsys):
    work = make_clone(tmp_path)
    run_git(work, "tag", "v0.10.0")
    code, err = attempt(work, monkeypatch, capsys, "0.9.0")
    assert code == 1 and err.count(chr(10)) == 1 and "not greater" in err
