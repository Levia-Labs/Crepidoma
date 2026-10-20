import importlib.util
import json
import random
import sys
from pathlib import Path

import pytest

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


HOSTILE = [
    "-x/y",
    "--config=/evil",
    "a/b -c",
    "a/b&calc",
    "a/b|calc",
    "a/b<x",
    "a/b>x",
    "a/b^x",
    "a/b%PATH%",
    'a/b"c',
    "a/b'c",
    "a/b`c`",
    "a/b\nc",
    "a b/c",
    "a/b/c",
    "",
    "https://x.test/a b",
    "https://x.test/a&b",
    "https://x.test/a|b",
    "https://x.test/a%41",
    "https://x.test/a" + chr(92) + "b",
    "http://x.test/a",
    "ftp://x.test/a",
    "-https://x.test/a",
]
HOSTILE_IDS = [
    "-x@y",
    "x@-y",
    "x@y -z",
    "x@y&calc",
    "x@y|calc",
    "x@y<z",
    "x@y>z",
    "x@y^z",
    "x@y%z%",
    'x@y"z',
    "x@y'z",
    "x@y`z`",
    "X@y",
    "x y@z",
    "x@y\nz",
    "no-at-sign",
    "@y",
    "x@",
    "",
]


def hostile_settings(tmp_path, monkeypatch, repo, plugin):
    settings = tmp_path / "settings.json"
    config = {
        "enabledPlugins": {plugin: True},
        "extraKnownMarketplaces": {"m": {"source": {"repo": repo}}},
    }
    settings.write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.setattr(plugins, "SETTINGS", settings)
    monkeypatch.setattr(plugins, "INSTALLED", tmp_path / "absent.json")


@pytest.mark.parametrize("repo", HOSTILE)
def test_hostile_repo_never_reaches_claude(tmp_path, monkeypatch, capsys, repo):
    hostile_settings(tmp_path, monkeypatch, repo, "good@market")
    calls = []
    monkeypatch.setattr(plugins, "claude", lambda *args: calls.append(args) or 0)
    if not repo:  # an empty repo is skipped silently, as before
        assert plugins.main(["--install"]) == 0
        return
    assert plugins.main(["--install"]) == 1
    assert not any("marketplace" in call for call in calls)
    assert ("plugin", "install", "good@market", "-y") in calls
    assert "invalid marketplace repo" in capsys.readouterr().err


@pytest.mark.parametrize("plugin", HOSTILE_IDS)
def test_hostile_plugin_id_never_reaches_claude(tmp_path, monkeypatch, capsys, plugin):
    hostile_settings(tmp_path, monkeypatch, "owner/repo", plugin)
    calls = []
    monkeypatch.setattr(plugins, "claude", lambda *args: calls.append(args) or 0)
    assert plugins.main(["--install"]) == 1
    assert ("plugin", "marketplace", "add", "owner/repo") in calls
    assert not any("install" in call for call in calls)
    assert "invalid plugin id" in capsys.readouterr().err


@pytest.mark.parametrize("repo", ["owner/repo", "a.b_c/d-e.f", "https://github.com/o/r.git"])
def test_valid_repos_pass(tmp_path, monkeypatch, repo):
    hostile_settings(tmp_path, monkeypatch, repo, "good@market")
    calls = []
    monkeypatch.setattr(plugins, "claude", lambda *args: calls.append(args) or 0)
    assert plugins.main(["--install"]) == 0
    assert ("plugin", "marketplace", "add", repo) in calls


BAD = set(" \t\r\n&|<>^%\"'`\\;$()")


@pytest.mark.parametrize("seed", range(20))
def test_accepted_values_never_hold_shell_metacharacters(seed):
    alphabet = "ab-_.@/:" + "".join(sorted(BAD))
    rng = random.Random(seed)  # noqa: S311 - test data, not security
    for _ in range(300):
        text = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 12)))
        for value in (text, "o/" + text, "https://h/" + text):
            if plugins.valid_repo(value):
                assert not BAD & set(value)
                assert not value.startswith("-")
        if plugins.valid_plugin_id(text):
            assert not BAD & set(text)
            assert not text.startswith("-")
