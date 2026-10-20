#!/usr/bin/env python3
"""Copy the plugins installed at user scope into .claude/marketplace/, a local marketplace.

A fresh, hardened machine reaches no plugin marketplace until the whitelist allows it, and a
plugin fetched later is whatever version upstream holds that day. The copy pins the version
this machine runs and installs offline:

  claude plugin marketplace add ./.claude/marketplace
  claude plugin install <name>@vendored -y

Each plugin is copied whole from its installPath in ~/.claude/plugins/installed_plugins.json,
licence included, without .git, node_modules or caches. Where two marketplaces carry a plugin
of the same name, the one .claude/settings.json enables wins.

Usage:
  python3 vendor_plugins.py            # copy; one line per plugin
  python3 vendor_plugins.py --dry-run  # what would be copied, and its size
  python3 vendor_plugins.py --check    # vendored versions against installed
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd())
SETTINGS = ROOT / ".claude" / "settings.json"
INSTALLED = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
MARKET = ROOT / ".claude" / "marketplace"
MARKET_NAME = "vendored"
IGNORE = shutil.ignore_patterns(".git", "node_modules", "__pycache__", "*.pyc", ".DS_Store")


def load(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def chosen() -> dict[str, dict]:
    """Plugin name -> {id, version, path}: the user-scope install, enabled id preferred."""
    enabled = {k for k, on in load(SETTINGS).get("enabledPlugins", {}).items() if on}
    picks: dict[str, dict] = {}
    for plugin_id, entries in sorted(load(INSTALLED).get("plugins", {}).items()):
        entry = next((e for e in entries if e.get("scope") == "user"), None)
        name = plugin_id.split("@", 1)[0]
        # Anthropic's own names cannot be republished; such a plugin installs from its
        # official marketplace, which claude:skills:setup already does.
        if entry is None or not entry.get("installPath") or reserved(name):
            continue
        if name in picks and picks[name]["id"] in enabled:
            continue
        picks[name] = {
            "id": plugin_id,
            "version": str(entry.get("version", "")),
            "path": Path(entry["installPath"]),
        }
    return picks


def size(path: Path) -> tuple[int, int]:
    files = [p for p in path.rglob("*") if p.is_file() and ".git" not in p.parts]
    return len(files), sum(p.stat().st_size for p in files)


def reserved(name: str) -> bool:
    """Names `claude plugin validate` refuses in a third-party marketplace."""
    if name in ("claude", "anthropic", "anthropics", "claude-code", "claude-mods"):
        return True
    return name.startswith(("claude-", "anthropic-", "anthropics-", "cc-plugin-"))


def manifest(picks: dict[str, dict]) -> dict:
    plugins = []
    for name, pick in sorted(picks.items()):
        meta = load(MARKET / name / ".claude-plugin" / "plugin.json")
        entry = {
            "name": name,
            "source": f"./{name}",
            "description": meta.get("description", f"Vendored from {pick['id']}"),
        }
        # plugin.json wins at install time; an entry version that disagrees is ignored and
        # warned about, so the entry carries one only when plugin.json does.
        if meta.get("version"):
            entry["version"] = meta["version"]
        plugins.append(entry)
    return {
        "name": MARKET_NAME,
        "owner": {"name": MARKET_NAME},
        "description": "Plugins this repository's sessions run, vendored for offline install",
        "plugins": plugins,
    }


def vendor(picks: dict[str, dict]) -> int:
    # A plugin uninstalled since the last copy leaves the marketplace with it.
    for stale in MARKET.glob("*/") if MARKET.is_dir() else []:
        if stale.name not in picks and stale.name != ".claude-plugin":
            shutil.rmtree(stale)
            print(f"{stale.name}: removed, no longer installed")
    for name, pick in sorted(picks.items()):
        dest = MARKET / name
        if not pick["path"].is_dir():
            print(f"{name}: missing {pick['path']}")
            continue
        shutil.rmtree(dest, ignore_errors=True)
        shutil.copytree(pick["path"], dest, ignore=IGNORE)
        files, total = size(dest)
        print(f"{name}  {pick['version']}  {files} files  {total // 1024} KB  from {pick['id']}")
    (MARKET / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    (MARKET / ".claude-plugin" / "marketplace.json").write_text(
        json.dumps(manifest(picks), indent=2) + "\n", encoding="utf-8"
    )
    # The installed version (often a commit) is what --check compares; the manifest can only
    # carry plugin.json's, and most plugins declare none.
    versions = {name: pick["version"] for name, pick in sorted(picks.items())}
    versions_file().write_text(json.dumps(versions, indent=2) + "\n", encoding="utf-8")
    return 0


def versions_file() -> Path:
    # Computed, not a constant, so a test that moves MARKET moves this with it.
    return MARKET / "versions.json"


def check(picks: dict[str, dict]) -> int:
    recorded = load(versions_file())
    drift = [
        f"{name}: vendored {recorded.get(name, 'none')}, installed {pick['version']}"
        for name, pick in sorted(picks.items())
        if recorded.get(name) != pick["version"]
    ]
    for line in drift:
        print(line)
    print(f"{len(picks) - len(drift)} of {len(picks)} vendored plugin(s) current")
    return 1 if drift else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Vendor user-scope plugins into the repo.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    picks = chosen()
    if not picks:
        print(f"no user-scope plugins in {INSTALLED}")
        return 1
    if args.check:
        return check(picks)
    if args.dry_run:
        for name, pick in sorted(picks.items()):
            files, total = size(pick["path"]) if pick["path"].is_dir() else (0, 0)
            print(f"{name}  {pick['version']}  {files} files  {total // 1024} KB  {pick['id']}")
        return 0
    return vendor(picks)


if __name__ == "__main__":
    sys.exit(main())
