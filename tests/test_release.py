import json
from pathlib import Path

import release


def setup_repo(root: Path) -> Path:
    manifest = root / "plugins/crepidoma-core/.claude-plugin/plugin.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps({"name": "crepidoma-core", "version": "0.1.0"}), encoding="utf-8"
    )
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
