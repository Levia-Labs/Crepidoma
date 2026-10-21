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
DEFAULT_BRANCH = "main"
HEADER = "# Changelog\n"
TEMPLATE = Path("templates/.pre-commit-config.yaml")
HOOKS_REPO = re.compile(r"(repo: \S*/Crepidoma\s+rev: )\S+")


def bump(root: Path, version: str, today: str) -> list[Path]:
    manifest = root / MANIFEST
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["version"] = version
    manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")
    changelog = root / "CHANGELOG.md"
    body = changelog.read_text(encoding="utf-8").removeprefix(HEADER).lstrip("\n")
    entry = f"{HEADER}\n## v{version} - {today}\n" + (f"\n{body}" if body else "")
    changelog.write_text(entry, encoding="utf-8", newline="\n")
    template = root / TEMPLATE
    text = template.read_text(encoding="utf-8")
    pinned = HOOKS_REPO.sub(lambda m: f"{m.group(1)}v{version}", text)
    template.write_text(pinned, encoding="utf-8", newline="\n")
    return [manifest, changelog, template]


def git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, encoding="utf-8"
    )


def preflight(root: Path, version: str) -> str | None:
    """Return a refusal message, or None when the release may proceed."""
    branch = git(root, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if branch != DEFAULT_BRANCH:
        return f"refusing: on branch {branch!r}, releases run from {DEFAULT_BRANCH}"
    if git(root, "status", "--porcelain", "--untracked-files=no").stdout.strip():
        return "refusing: working tree has tracked changes"
    fetched = git(root, "fetch", "--quiet", "origin")
    if fetched.returncode:
        return f"refusing: git fetch failed: {fetched.stderr.strip()}"
    local = git(root, "rev-parse", DEFAULT_BRANCH).stdout.strip()
    remote = git(root, "rev-parse", f"origin/{DEFAULT_BRANCH}").stdout.strip()
    if local != remote:
        return f"refusing: local {DEFAULT_BRANCH} differs from origin/{DEFAULT_BRANCH}"
    tags = set(git(root, "tag", "--list", "v*").stdout.split())
    listed = git(root, "ls-remote", "--tags", "origin", "refs/tags/v*")
    if listed.returncode:
        return f"refusing: cannot list origin tags: {listed.stderr.strip()}"
    for line in listed.stdout.splitlines():
        ref = line.split("	")[-1].removeprefix("refs/tags/")
        tags.add(ref.removesuffix("^{}"))
    if f"v{version}" in tags:
        return f"refusing: tag v{version} already exists"
    versions = [tuple(map(int, t[1:].split("."))) for t in tags if SEMVER.match(t[1:])]
    if versions and tuple(map(int, version.split("."))) <= max(versions):
        latest = ".".join(map(str, max(versions)))
        return f"refusing: {version} is not greater than latest tag v{latest}"
    return None


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
    refusal = preflight(ROOT, args.version)
    if refusal:
        print(refusal, file=sys.stderr)
        return 1
    changed = bump(ROOT, args.version, datetime.date.today().isoformat())
    subprocess.run(["git", "-C", str(ROOT), "add", *map(str, changed)], check=True)
    message = f"chore(release): v{args.version}"
    subprocess.run(["git", "-C", str(ROOT), "commit", "-m", message], check=True)
    subprocess.run(["git", "-C", str(ROOT), "tag", f"v{args.version}"], check=True)
    print(f"tagged v{args.version}; push with: git push origin main v{args.version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
