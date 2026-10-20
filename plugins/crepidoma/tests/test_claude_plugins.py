import importlib.util
import json
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "claude" / "plugins.py"
spec = importlib.util.spec_from_file_location("claude_plugins", SCRIPT)
plugins = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = plugins
spec.loader.exec_module(plugins)


SETTINGS = {
    "enabledPlugins": {
        "caveman@caveman": True,
        "superpowers@claude-plugins-official": True,
        "feature-dev@claude-plugins-official": True,
        "old@claude-plugins-official": False,
    },
    "extraKnownMarketplaces": {"caveman": {"source": {"source": "github", "repo": "J/caveman"}}},
}
INSTALLED = {"version": 2, "plugins": {"caveman@caveman": [], "superpowers@x": []}}


def files(tmp_path, monkeypatch):
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps(SETTINGS), encoding="utf-8")
    installed = tmp_path / "installed_plugins.json"
    installed.write_text(json.dumps(INSTALLED), encoding="utf-8")
    monkeypatch.setattr(plugins, "SETTINGS", settings)
    monkeypatch.setattr(plugins, "INSTALLED", installed)


def test_missing_lists_enabled_plugins_not_installed(tmp_path, monkeypatch):
    files(tmp_path, monkeypatch)
    # Matched by the full id: superpowers from another marketplace is not this one.
    assert plugins.missing() == [
        "feature-dev@claude-plugins-official",
        "superpowers@claude-plugins-official",
    ]


def test_check_prints_one_line_per_missing_plugin(tmp_path, monkeypatch, capsys):
    files(tmp_path, monkeypatch)
    assert plugins.main(["--check"]) == 1
    out = capsys.readouterr().out.splitlines()
    assert out[-1] == "2 of 3 enabled plugin(s) not installed - run: task claude:skills:setup"


def test_check_passes_quietly_when_all_installed(tmp_path, monkeypatch, capsys):
    files(tmp_path, monkeypatch)
    monkeypatch.setattr(plugins, "missing", list)
    assert plugins.main(["--check"]) == 0
    assert capsys.readouterr().out.strip() == "3 enabled plugin(s) installed"


def test_install_adds_marketplaces_then_installs_the_missing(tmp_path, monkeypatch):
    files(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setattr(plugins, "claude", lambda *args: calls.append(args) or 0)
    assert plugins.main(["--install"]) == 0
    assert calls[0] == ("plugin", "marketplace", "add", "J/caveman")
    assert ("plugin", "install", "feature-dev@claude-plugins-official", "-y") in calls


def test_claude_missing_from_path_is_127(monkeypatch, capsys):
    monkeypatch.setattr(plugins.shutil, "which", lambda name: None)
    assert plugins.claude("plugin", "list") == 127
    assert "not on PATH" in capsys.readouterr().out


def test_unreadable_files_count_as_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(plugins, "SETTINGS", tmp_path / "absent.json")
    monkeypatch.setattr(plugins, "INSTALLED", tmp_path / "absent.json")
    assert plugins.missing() == []
