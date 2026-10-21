"""OAuth token for budget.py: the Claude credentials file, or the macOS login Keychain."""

import json
import subprocess
import sys
from pathlib import Path

# macOS keeps the credentials blob in the login Keychain under this service, not on disk.
KEYCHAIN_SERVICE = "Claude Code-credentials"


def credentials_path() -> Path:
    return Path.home() / ".claude" / ".credentials.json"


def file_credentials() -> dict | None:
    try:
        data = json.loads(credentials_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def keychain_credentials() -> dict | None:
    """The same blob from the macOS login Keychain; read into memory, never printed."""
    if sys.platform != "darwin":
        return None
    try:
        done = subprocess.run(
            ["/usr/bin/security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    try:
        data = json.loads(done.stdout)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def token() -> str | None:
    data = file_credentials() or keychain_credentials()
    if not data:
        return None
    oauth = data.get("claudeAiOauth")
    return (oauth.get("accessToken") or None) if isinstance(oauth, dict) else None
