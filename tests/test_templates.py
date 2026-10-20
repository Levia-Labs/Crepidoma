import json
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"


def test_settings_template_links_marketplace():
    data = json.loads((TEMPLATES / "settings.json").read_text(encoding="utf-8"))
    source = data["extraKnownMarketplaces"]["levia-labs"]["source"]
    assert source == {"source": "github", "repo": "Levia-Labs/Crepidoma"}
    assert data["enabledPlugins"]["crepidoma-core@levia-labs"] is True
    assert "hooks" not in data


def test_precommit_template_links_repo():
    text = (TEMPLATES / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    assert "repo: https://github.com/Levia-Labs/Crepidoma" in text
    assert "id: crepidoma-scrub" in text


def test_taskfile_includes_point_into_submodule():
    text = (TEMPLATES / "Taskfile.includes.yml").read_text(encoding="utf-8")
    assert ".crepidoma/taskfiles/claude" in text
    assert ".crepidoma/taskfiles/lint" in text


def test_claude_md_skeleton_names_plugin():
    text = (TEMPLATES / "CLAUDE.md").read_text(encoding="utf-8")
    assert "crepidoma-core" in text.splitlines()[2]


def test_marketplace_is_named_levia_labs():
    root = TEMPLATES.parent
    data = json.loads((root / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    assert data["name"] == "levia-labs"
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert "claude plugin install crepidoma-core@levia-labs" in readme
    assert "@crepidoma " not in readme and '@crepidoma"' not in readme
