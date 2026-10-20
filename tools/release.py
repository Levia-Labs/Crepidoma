"""Bump the plugin version, prepend a CHANGELOG entry, commit and tag. Never pushes.

Usage: release.py VERSION [--dry-run]
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = Path("plugins/crepidoma/.claude-plugin/plugin.json")
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
HEADER = "# Changelog\n"


def bump(root: Path, version: str, today: str) -> list[Path]:
    manifest = root / MANIFEST
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["version"] = version
    manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")
    changelog = root / "CHANGELOG.md"
    body = changelog.read_text(encoding="utf-8").removeprefix(HEADER).lstrip("\n")
    entry = f"{HEADER}\n## v{version} - {today}\n" + (f"\n{body}" if body else "")
    changelog.write_text(entry, encoding="utf-8", newline="\n")
    return [manifest, changelog]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if not SEMVER.match(args.version):
        print(f"not semver: {args.version}", file=sys.stderr)
        return 2
    if args.dry_run:
        print(f"would release v{args.version}")
        return 0
    changed = bump(ROOT, args.version, datetime.date.today().isoformat())
    subprocess.run(["git", "-C", str(ROOT), "add", *map(str, changed)], check=True)
    message = f"chore(release): v{args.version}"
    subprocess.run(["git", "-C", str(ROOT), "commit", "-m", message], check=True)
    subprocess.run(["git", "-C", str(ROOT), "tag", f"v{args.version}"], check=True)
    print(f"tagged v{args.version}; push with: git push origin main v{args.version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
