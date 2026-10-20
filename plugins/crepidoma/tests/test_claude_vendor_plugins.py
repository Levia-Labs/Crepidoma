import importlib.util
import json
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "claude" / "vendor_plugins.py"
spec = importlib.util.spec_from_file_location("claude_vendor_plugins", SCRIPT)
vendor = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = vendor
spec.loader.exec_module(vendor)


def setup(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    for name in ("one", "dup-a", "dup-b"):
        (cache / name / ".git").mkdir(parents=True)
        (cache / name / ".git" / "HEAD").write_text("x", encoding="utf-8")
        (cache / name / "LICENSE").write_text("MIT", encoding="utf-8")
    installed = {
        "plugins": {
            "one@m": [{"scope": "user", "installPath": str(cache / "one"), "version": "1"}],
            "dup@a": [{"scope": "user", "installPath": str(cache / "dup-a"), "version": "a"}],
            "dup@b": [{"scope": "user", "installPath": str(cache / "dup-b"), "version": "b"}],
            "proj@m": [{"scope": "project", "installPath": str(cache / "one"), "version": "p"}],
        }
    }
    (tmp_path / "installed.json").write_text(json.dumps(installed), encoding="utf-8")
    settings = {"enabledPlugins": {"dup@a": True}}
    (tmp_path / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
    monkeypatch.setattr(vendor, "INSTALLED", tmp_path / "installed.json")
    monkeypatch.setattr(vendor, "SETTINGS", tmp_path / "settings.json")
    monkeypatch.setattr(vendor, "MARKET", tmp_path / "market")


def test_chosen_takes_user_scope_and_prefers_the_enabled_id(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    picks = vendor.chosen()
    assert sorted(picks) == ["dup", "one"]
    assert picks["dup"]["id"] == "dup@a"


def test_vendor_copies_without_git_and_writes_the_manifest(tmp_path, monkeypatch, capsys):
    setup(tmp_path, monkeypatch)
    assert vendor.main([]) == 0
    market = tmp_path / "market"
    assert (market / "one" / "LICENSE").is_file()
    assert not (market / "one" / ".git").exists()
    manifest = json.loads(
        (market / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
    )
    assert [p["source"] for p in manifest["plugins"]] == ["./dup", "./one"]
    assert len(capsys.readouterr().out.splitlines()) == 2


def test_check_reports_drift(tmp_path, monkeypatch, capsys):
    setup(tmp_path, monkeypatch)
    vendor.main([])
    capsys.readouterr()
    assert vendor.main(["--check"]) == 0
    installed = json.loads((tmp_path / "installed.json").read_text(encoding="utf-8"))
    installed["plugins"]["one@m"][0]["version"] = "2"
    (tmp_path / "installed.json").write_text(json.dumps(installed), encoding="utf-8")
    assert vendor.main(["--check"]) == 1
    assert "one: vendored 1, installed 2" in capsys.readouterr().out


def test_reserved_names_are_skipped_and_stale_copies_removed(tmp_path, monkeypatch, capsys):
    setup(tmp_path, monkeypatch)
    assert vendor.reserved("claude-code-setup")
    assert not vendor.reserved("caveman")
    (tmp_path / "market" / "gone").mkdir(parents=True)
    vendor.main([])
    assert not (tmp_path / "market" / "gone").exists()
    assert "gone: removed" in capsys.readouterr().out


def test_dry_run_copies_nothing(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    assert vendor.main(["--dry-run"]) == 0
    assert not (tmp_path / "market").exists()


def test_nothing_installed_is_an_error(tmp_path, monkeypatch):
    monkeypatch.setattr(vendor, "INSTALLED", tmp_path / "absent.json")
    assert vendor.main([]) == 1
