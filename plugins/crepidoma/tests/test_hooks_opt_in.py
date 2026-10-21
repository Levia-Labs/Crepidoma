"""Opt-in: the plugin's hooks stay inert in a project that did not enable it."""

import json

import hooks
import hooks_stop
import pytest
from hooks_patch import patch_shared


def write_settings(root, plugins):
    settings = root / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(json.dumps({"enabledPlugins": plugins}), encoding="utf-8")


@pytest.mark.no_opt_in
def test_opt_in_requires_project_enabled_plugin(tmp_path, monkeypatch):
    patch_shared(monkeypatch, "ROOT", tmp_path)
    assert hooks.opted_in() is False
    write_settings(tmp_path, {"crepidoma@levia-labs": False})
    assert hooks.opted_in() is False
    write_settings(tmp_path, {"crepidoma@levia-labs": True})
    assert hooks.opted_in() is True


@pytest.mark.no_opt_in
def test_malformed_settings_is_not_opt_in(tmp_path, monkeypatch):
    patch_shared(monkeypatch, "ROOT", tmp_path)
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.json").write_text("{not json", encoding="utf-8")
    assert hooks.opted_in() is False


@pytest.mark.no_opt_in
def test_stop_runs_no_project_code_without_opt_in(tmp_path, monkeypatch):
    patch_shared(monkeypatch, "ROOT", tmp_path)
    marker = tmp_path / "dirty"
    marker.write_text("", encoding="utf-8")
    gate = hooks_stop.GATES[0]._replace(marker=marker)
    monkeypatch.setattr(hooks_stop, "GATES", (gate,))
    calls = []
    monkeypatch.setattr(hooks_stop, "run", lambda *args, **kw: calls.append(args))
    assert hooks.stop({}) == 0
    assert calls == []


@pytest.mark.no_opt_in
def test_project_budget_script_never_preferred_over_plugin(tmp_path, monkeypatch):
    patch_shared(monkeypatch, "ROOT", tmp_path)
    script = tmp_path / hooks.BUDGET_SCRIPTS[0]
    script.parent.mkdir(parents=True)
    script.write_text("", encoding="utf-8")
    assert hooks.budget_script() != script
