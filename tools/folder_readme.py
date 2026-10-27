"""Keep a README.md in every tracked folder with a generated contents list.

Usage: folder_readme.py {update|check} [--purposes docs/folder-purposes.toml]
       folder_readme.py add <path> "<purpose>" [--replace] [--purposes ...]
update writes missing READMEs and refreshes the block between the contents markers;
hand-written text outside the markers, and READMEs without markers, are left alone.
check exits 1 and names each folder whose README is missing or stale.
add sets a folder or file purpose in the purposes TOML (sorted, refuses a duplicate unless
--replace) and regenerates the READMEs.

Purposes TOML: [folders] keys are repo-relative folders; [files] keys are repo-relative paths
("indexer/query/entity_test.go", forward slashes on every OS) or, as fallback, basenames.
`include = ["docs/folder-purposes.d/*.toml"]` in the main file merges more files (globs relative
to the main file); a key defined in two files is an error naming both.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import tomllib
from pathlib import Path

MARK_START = "<!-- contents:start -->"
MARK_END = "<!-- contents:end -->"
# Agent loaders read every .md in the agents folders as an agent definition, and GitHub shows
# .github/README.md on the repository home page in place of the root README.
EXCLUDED = {".claude/agents", "plugins/crepidoma/agents", ".github"}
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


def norm(key: str) -> str:
    """Purpose keys use forward slashes on every OS, so a Windows-style key still matches."""
    return key.replace("\\", "/").removeprefix("./")


def load_purposes(main: Path) -> tuple[dict, dict[tuple[str, str], Path]]:
    """Merge the main purposes file with its `include` globs; also map each key to its file."""
    if not main.is_file():
        return {}, {}
    data = tomllib.loads(main.read_text(encoding="utf-8"))
    sources = [main, *sorted(p for g in data.pop("include", []) for p in main.parent.glob(g))]
    merged: dict[str, dict[str, str]] = {}
    origin: dict[tuple[str, str], Path] = {}
    for src in sources:
        part = data if src == main else tomllib.loads(src.read_text(encoding="utf-8"))
        part.pop("include", None)
        for table, entries in part.items():
            for key, value in entries.items():
                key = norm(key)
                if (table, key) in origin:
                    raise SystemExit(
                        f"duplicate purpose [{table}] {key!r} in {origin[(table, key)]} and {src}"
                    )
                origin[(table, key)] = src
                merged.setdefault(table, {})[key] = value
    return merged, origin


def set_purpose(text: str, table: str, key: str, value: str, replace: bool) -> str:
    """Insert or replace one `"key" = "value"` line in a purposes file, keeping comments."""
    lines = text.splitlines()
    new = f"{json.dumps(key)} = {json.dumps(value)}"
    start = next((i for i, ln in enumerate(lines) if ln.strip() == f"[{table}]"), None)
    if start is None:
        return text.rstrip("\n") + f"\n\n[{table}]\n{new}\n"
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("[")), len(lines))
    at = end
    while at > start + 1 and not lines[at - 1].strip():
        at -= 1  # keep blank lines that separate tables below the new entry
    for i in range(start + 1, end):
        found = re.match(r'\s*"((?:[^"\\]|\\.)*)"\s*=', lines[i])
        if not found:
            continue
        current = norm(json.loads(f'"{found.group(1)}"'))
        if current == key:
            if not replace:
                raise SystemExit(f"[{table}] {key!r} exists; pass --replace")
            lines[i] = new
            return "\n".join(lines) + "\n"
        if current > key and i < at:
            at = i  # first larger key: insert before it to stay sorted
    lines.insert(at, new)
    return "\n".join(lines) + "\n"


def add(root: Path, files: list[str], main: Path, path: str, text: str, replace: bool) -> str:
    """Set the purpose of a folder or file; returns the table used."""
    key = norm(path).strip("/")
    if any(f.startswith(key + "/") for f in files):
        table = "folders"
    elif key in files:
        table = "files"
    else:
        raise SystemExit(f"{key}: not a tracked folder or file")
    _, origin = load_purposes(main)
    target = origin.get((table, key), main)
    if (table, key) in origin and not replace:
        raise SystemExit(f"[{table}] {key!r} exists in {target}; pass --replace")
    body = target.read_text(encoding="utf-8") if target.is_file() else ""
    target.write_text(set_purpose(body, table, key, text, replace), encoding="utf-8", newline="\n")
    return table


def describe(path: Path, overrides: dict[str, str], rel: str = "") -> str:
    # Path key first so same-named files in different folders can differ; basename is the fallback.
    keyed = {norm(k): v for k, v in overrides.items()}
    if rel and norm(rel) in keyed:
        return keyed[norm(rel)]
    if path.name in keyed:
        return keyed[path.name]
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
        text = describe(root / folder / name, overrides, f"{folder}/{name}")
        lines.append(f"- [`{name}`]({name}) - {text}")
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
    parser.add_argument("mode", choices=["update", "check", "add"])
    parser.add_argument("target", nargs="*", help="add: <path> <purpose text>")
    parser.add_argument("--purposes", type=Path, default=Path("docs/folder-purposes.toml"))
    parser.add_argument("--replace", action="store_true", help="add: overwrite an existing purpose")
    args = parser.parse_args(argv)
    root = Path.cwd()
    listing = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True)
    files = [f for f in listing.stdout.splitlines() if f]
    if args.mode == "add":
        if len(args.target) != 2:
            parser.error("add needs <path> and <purpose text>")
        table = add(root, files, args.purposes, *args.target, replace=args.replace)
        purposes, _ = load_purposes(args.purposes)
        update(root, files, purposes, EXCLUDED)
        print(f"[{table}] {norm(args.target[0])} set; READMEs refreshed")
        return 0
    purposes, _ = load_purposes(args.purposes)
    if args.mode == "check":
        return check(root, files, purposes, EXCLUDED)
    changed = update(root, files, purposes, EXCLUDED)
    print(f"{len(changed)} READMEs written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
