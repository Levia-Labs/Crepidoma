import json
import re
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"


def test_settings_template_links_marketplace():
    data = json.loads((TEMPLATES / "settings.json").read_text(encoding="utf-8"))
    source = data["extraKnownMarketplaces"]["levia-labs"]["source"]
    assert source == {"source": "github", "repo": "Levia-Labs/Crepidoma", "ref": "main"}
    assert data["enabledPlugins"]["crepidoma@levia-labs"] is True
    assert "hooks" not in data


def test_precommit_template_links_repo():
    text = (TEMPLATES / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    assert "repo: https://github.com/Levia-Labs/Crepidoma" in text
    assert "id: crepidoma-scrub" in text
    assert "id: crepidoma-scrub-msg" in text
    assert "commit-msg" in text


def test_taskfile_includes_point_into_submodule():
    text = (TEMPLATES / "Taskfile.includes.yml").read_text(encoding="utf-8")
    assert ".crepidoma/taskfiles/claude" in text
    assert ".crepidoma/taskfiles/lint" in text


def test_claude_md_skeleton_names_plugin():
    text = (TEMPLATES / "CLAUDE.md").read_text(encoding="utf-8")
    assert "crepidoma plugin" in text.splitlines()[2]


def test_marketplace_is_named_levia_labs():
    root = TEMPLATES.parent
    data = json.loads((root / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    assert data["name"] == "levia-labs"
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert "claude plugin install crepidoma@levia-labs" in readme
    assert "@crepidoma " not in readme and '@crepidoma"' not in readme


def test_plugin_is_named_crepidoma():
    root = TEMPLATES.parent
    data = json.loads((root / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    assert [p["name"] for p in data["plugins"]] == ["crepidoma"]
    assert data["plugins"][0]["source"] == "./plugins/crepidoma"
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert "claude plugin install crepidoma@levia-labs" in readme
    assert "crepidoma-core" not in readme


def test_templates_pin_opus_main_thread():
    for settings in (TEMPLATES / "settings.json", TEMPLATES.parent / ".claude" / "settings.json"):
        data = json.loads(settings.read_text(encoding="utf-8"))
        assert data["model"] == "claude-opus-5-5", settings
        assert data.get("env", {}).get("CLAUDE_CODE_SUBAGENT_MODEL") in ("sonnet", None)


def test_template_is_bash_only_and_subagents_default_to_sonnet():
    data = json.loads((TEMPLATES / "settings.json").read_text(encoding="utf-8"))
    perms = data["permissions"]
    assert "PowerShell" in perms["deny"]
    assert not [rule for rule in perms["allow"] if rule.startswith("PowerShell")]
    assert data["env"]["CLAUDE_CODE_SUBAGENT_MODEL"] == "sonnet"
    assert "Bash(rm -rf *)" in perms["deny"]
    assert data["enabledPlugins"]["caveman@caveman"] is True


def test_template_has_no_wrapper_allows():
    data = json.loads((TEMPLATES / "settings.json").read_text(encoding="utf-8"))
    wrappers = ("uv run", "xargs", "find ", "python", "bash -c", "sh -c", "env ")
    for rule in data["permissions"]["allow"]:
        assert not any(w in rule for w in wrappers), rule


def test_templates_track_main():
    root = TEMPLATES.parent
    hooks = (TEMPLATES / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    assert re.search(r"Crepidoma\s+rev: v\d+\.\d+\.\d+\n", hooks)
    assert "rev: main" not in hooks
    assert "reusable-validate.yml@main" in (TEMPLATES / "ci.yml").read_text(encoding="utf-8")
    assert "-b main" in (TEMPLATES / "gitmodules.txt").read_text(encoding="utf-8")
    assert "rev: v0" not in (root / "README.md").read_text(encoding="utf-8")


def test_ci_template_pins_tools_and_checks_out_full_history():
    text = (TEMPLATES / "ci.yml").read_text(encoding="utf-8")
    for pin in ("0.11.0", "3.14.1", "8.30.1", "hadolint"):
        assert pin in text
    assert "submodules: true" in text
    assert "fetch-depth: 0" in text
    assert "task lint:check" in text
    assert "task security:check" in text


def test_ci_template_verifies_downloads_against_pinned_sha256():
    text = (TEMPLATES / "ci.yml").read_text(encoding="utf-8")
    assert "sha256sum -c -" in text
    assert len(re.findall(r"^\s+[0-9a-f]{64} \w", text, re.M)) == 4
    assert not re.search(r"curl[^\n]*\|", text)
    assert not re.search(r"curl[^\n]*\\\n\s*\|", text)


def test_migration_documents_ci_tools():
    text = (TEMPLATES.parent / "docs" / "migration.md").read_text(encoding="utf-8")
    assert "fetch-depth: 0" in text
    assert "8.30.1" in text
