#!/usr/bin/env python3
"""Install, or report, the plugins .claude/settings.json enables.

Enabling a plugin in the project settings does not install it: an enabled plugin that is not
installed contributes no skills, agents or hooks, silently.

Matched by full id, `name@marketplace`: superpowers from obra's marketplace is not the
superpowers this project enables from claude-plugins-official.

Usage:
  python3 plugins.py --check     # one line per missing plugin; exit 1 if any
  python3 plugins.py --install   # add the marketplaces, install what is missing
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd())
SETTINGS = ROOT / ".claude" / "settings.json"
INSTALLED = Path.home() / ".claude" / "plugins" / "installed_plugins.json"


# Values come from settings JSON and reach `claude`, which on Windows may be a .cmd shim run
# through cmd.exe: anything outside these shapes is refused, never passed on.
REPO = re.compile(r"^(?:[A-Za-z0-9_][A-Za-z0-9_.-]*/[A-Za-z0-9_][A-Za-z0-9_.-]*)$")
_UNSAFE = "\\s&|<>^%\"'`\\\\;$()"
URL = re.compile(f"^https://[^{_UNSAFE}-][^{_UNSAFE}]*$")
PLUGIN_ID = re.compile(r"^[a-z0-9][a-z0-9_.-]*@[a-z0-9][a-z0-9_.-]*$")


def valid_repo(value: object) -> bool:
    return isinstance(value, str) and bool(REPO.fullmatch(value) or URL.fullmatch(value))


def valid_plugin_id(value: object) -> bool:
    return isinstance(value, str) and bool(PLUGIN_ID.fullmatch(value))


def load(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def enabled() -> list[str]:
    return sorted(k for k, on in load(SETTINGS).get("enabledPlugins", {}).items() if on)


def missing() -> list[str]:
    installed = load(INSTALLED).get("plugins", {})
    return [plugin for plugin in enabled() if plugin not in installed]


def claude(*args: str) -> int:
    # Resolved, not passed by name: on Windows the CLI is claude.cmd, which CreateProcess does
    # not find from a bare "claude".
    binary = shutil.which("claude")
    if binary is None:
        print("claude: not on PATH - task claude:install")
        return 127
    return subprocess.run([binary, *args], check=False).returncode


def install() -> int:
    failed = 0
    # A marketplace already known makes `add` exit non-zero; the install that follows is
    # what decides success.
    for market in load(SETTINGS).get("extraKnownMarketplaces", {}).values():
        repo = (market.get("source") or {}).get("repo")
        if not repo:
            continue
        if valid_repo(repo):
            claude("plugin", "marketplace", "add", repo)
        else:
            print(f"invalid marketplace repo skipped: {repo!r}", file=sys.stderr)
            failed += 1
    for plugin in missing():
        if not valid_plugin_id(plugin):
            print(f"invalid plugin id skipped: {plugin!r}", file=sys.stderr)
            failed += 1
            continue
        # `-y` accepts the install prompt: task runs with no TTY attached.
        if claude("plugin", "install", plugin, "-y") != 0:
            print(f"install failed: {plugin}")
            failed += 1
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Enabled project plugins: check or install.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--install", action="store_true")
    args = parser.parse_args(argv)

    if args.install:
        return install()
    absent = missing()
    for plugin in absent:
        print(f"not installed: {plugin}")
    if absent:
        print(
            f"{len(absent)} of {len(enabled())} enabled plugin(s) not installed - "
            "run: task claude:skills:setup"
        )
        return 1
    print(f"{len(enabled())} enabled plugin(s) installed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
