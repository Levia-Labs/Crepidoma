"""Keep a README.md in every tracked folder with a generated contents list.

Usage: folder_readme.py {update|check} [--purposes docs/folder-purposes.toml]
update writes missing READMEs and refreshes the block between the contents markers;
hand-written text outside the markers, and READMEs without markers, are left alone.
check exits 1 and names each folder whose README is missing or stale.
"""

from __future__ import annotations

import argparse
import ast
import re
import subprocess
import tomllib
from pathlib import Path

MARK_START = "<!-- contents:start -->"
MARK_END = "<!-- contents:end -->"
# Agent loaders read every .md in these folders as an agent definition.
EXCLUDED = {".claude/agents", "plugins/crepidoma/agents"}
GENERIC = {
    ".json": "JSON data or config.",
    ".yml": "YAML config.",
    ".yaml": "YAML config.",
    ".toml": "TOML config.",
    ".baseline": "Ratchet baseline.",
    ".cmd": "Windows launcher.",
    ".js": "JavaScript config.",
}
BLOCK = re.compile(re.escape(MARK_START) + r".*?" + re.escape(MARK_END), re.DOTALL)


def describe(path: Path, overrides: dict[str, str]) -> str:
    if path.name in overrides:
        return overrides[path.name]
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.name == "Taskfile.yml":
        count = len(re.findall(r"^ {4}desc:", text, re.MULTILINE))
        return f"Task namespace with {count} tasks."
    if path.suffix == ".py":
        try:
            doc = ast.get_docstring(ast.parse(text))
        except SyntaxError:
            doc = None
        if doc:
            return doc.strip().splitlines()[0]
        if path.name.startswith("test_"):
            return f"Tests for `{path.stem.removeprefix('test_')}`."
        return "Python module."
    if path.suffix == ".md":
        found = re.search(r"^description:\s*(.+)$", text, re.MULTILINE)
        if text.startswith("---") and found:
            return found.group(1).strip()
        heading = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        return heading.group(1).strip() if heading else "Markdown document."
    if not path.suffix and path.parent.name == "bin":
        return "Launcher script."
    return GENERIC.get(path.suffix, "File.")


def folders(files: list[str], excluded: set[str]) -> list[str]:
    found: set[str] = set()
    for name in files:
        parts = name.split("/")[:-1]
        for depth in range(1, len(parts) + 1):
            found.add("/".join(parts[:depth]))
    return sorted(f for f in found if f not in excluded)


def title(folder: str) -> str:
    name = folder.rsplit("/", 1)[-1]
    return name if name.startswith(".") else name[:1].upper() + name[1:].replace("-", " ")


def contents(root: Path, folder: str, files: list[str], purposes: dict, excluded: set[str]) -> str:
    prefix = folder + "/"
    children = {n[len(prefix) :].split("/")[0] for n in files if n.startswith(prefix)}
    dirs = sorted(c for c in children if any(n.startswith(f"{prefix}{c}/") for n in files))
    names = sorted(c for c in children if c not in dirs and c != "README.md")
    overrides = purposes.get("files", {})
    lines = []
    for name in dirs:
        rel = f"{folder}/{name}"
        target = f"{name}/" if rel in excluded else f"{name}/README.md"
        lines.append(f"- [`{name}/`]({target}) - {purposes.get('folders', {}).get(rel, 'Folder.')}")
    for name in names:
        lines.append(f"- [`{name}`]({name}) - {describe(root / folder / name, overrides)}")
    # Blank lines around the list match prettier's Markdown output, so the two never fight.
    return MARK_START + "\n\n" + "\n".join(lines) + "\n\n" + MARK_END


def render(root: Path, folder: str, files: list[str], purposes: dict, excluded: set[str]) -> str:
    purpose = purposes.get("folders", {}).get(folder)
    head = f"# {title(folder)}\n\n" + (f"- {purpose}\n\n" if purpose else "")
    return head + "## Contents\n\n" + contents(root, folder, files, purposes, excluded) + "\n"


def wanted(root: Path, folder: str, files: list[str], purposes: dict, excluded: set[str]) -> str:
    """The README text this folder should have, or the current text when hand-written."""
    path = root / folder / "README.md"
    if not path.is_file():
        return render(root, folder, files, purposes, excluded)
    current = path.read_text(encoding="utf-8")
    if MARK_START not in current:
        return current
    block = contents(root, folder, files, purposes, excluded)
    return BLOCK.sub(lambda _: block, current, count=1)


def update(root: Path, files: list[str], purposes: dict, excluded: set[str]) -> list[str]:
    changed = []
    for folder in folders(files, excluded):
        path = root / folder / "README.md"
        text = wanted(root, folder, files, purposes, excluded)
        if not path.is_file() or path.read_text(encoding="utf-8") != text:
            path.write_text(text, encoding="utf-8", newline="\n")
            changed.append(folder)
    return changed


def check(root: Path, files: list[str], purposes: dict, excluded: set[str]) -> int:
    stale = []
    for folder in folders(files, excluded):
        path = root / folder / "README.md"
        text = wanted(root, folder, files, purposes, excluded)
        if not path.is_file() or path.read_text(encoding="utf-8") != text:
            stale.append(folder)
    for folder in stale[:20]:
        print(f"{folder}/README.md: missing or stale; run: task docs:readmes")
    return 1 if stale else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["update", "check"])
    parser.add_argument("--purposes", type=Path, default=Path("docs/folder-purposes.toml"))
    args = parser.parse_args(argv)
    root = Path.cwd()
    listing = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True)
    files = [f for f in listing.stdout.splitlines() if f]
    purposes = (
        tomllib.loads(args.purposes.read_text(encoding="utf-8")) if args.purposes.is_file() else {}
    )
    if args.mode == "check":
        return check(root, files, purposes, EXCLUDED)
    changed = update(root, files, purposes, EXCLUDED)
    print(f"{len(changed)} READMEs written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
