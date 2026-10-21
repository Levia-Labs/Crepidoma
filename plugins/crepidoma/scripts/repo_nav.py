"""Locate code without reading whole files: outline, section, tasks, diff.

Usage: repo_nav.py {outline PATH [--depth N] |
       section PATH NAME | tasks [--grep RE] | diff [--base REF]}
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

OUTLINE_MAX = 40
SECTION_MAX = 80
DIFF_MAX = 20
HEADING = re.compile(r"^(#{1,6})\s+(.*)")
YAML_TOP = re.compile(r"^([A-Za-z_][\w-]*):")
YAML_ENTRY = re.compile(r"^  ([A-Za-z_][\w:.-]*):")
FUNCS = (ast.FunctionDef, ast.AsyncFunctionDef)


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
    except OSError as error:
        return subprocess.CompletedProcess(cmd, 127, "", str(error))


def cap(rows: list[str], limit: int) -> list[str]:
    if len(rows) <= limit:
        return rows
    return [*rows[: limit - 1], f"... {len(rows) - limit + 1} more"]


def signature(node: ast.AST) -> str:
    args = ast.unparse(node.args)  # type: ignore[attr-defined]
    ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""  # type: ignore[attr-defined]
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    return f"{prefix} {node.name}({args}){ret}"  # type: ignore[attr-defined]


def outline_py(text: str, depth: int) -> list[str]:
    try:
        tree = ast.parse(text)
    except SyntaxError as error:
        return [f"{error.lineno}: syntax error: {error.msg}"]
    rows: list[str] = []

    def walk(body: list[ast.stmt], level: int) -> None:
        for node in body:
            pad = "  " * (level - 1)
            if isinstance(node, ast.ClassDef):
                rows.append(f"{node.lineno}: {pad}class {node.name}")
                if level < depth:
                    walk(node.body, level + 1)
            elif isinstance(node, FUNCS):
                rows.append(f"{node.lineno}: {pad}{signature(node)}")
                if level < depth:
                    walk(node.body, level + 1)

    walk(tree.body, 1)
    return rows


def outline_md(text: str, depth: int) -> list[str]:
    rows: list[str] = []
    fenced = False
    for number, line in enumerate(text.splitlines(), 1):
        if line.startswith("```"):
            fenced = not fenced
            continue
        match = None if fenced else HEADING.match(line)
        if match and len(match.group(1)) <= depth:
            rows.append(f"{number}: {'  ' * (len(match.group(1)) - 1)}{match.group(2).strip()}")
    return rows


def outline_yaml(text: str, depth: int) -> list[str]:
    rows: list[str] = []
    top = ""
    for number, line in enumerate(text.splitlines(), 1):
        match = YAML_TOP.match(line)
        if match:
            top = match.group(1)
            rows.append(f"{number}: {top}")
        elif depth >= 2 and top in ("tasks", "includes"):
            entry = YAML_ENTRY.match(line)
            if entry:
                rows.append(f"{number}:   {entry.group(1)}")
    return rows


def outline(path: Path, depth: int) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    suffix = path.suffix.lower()
    head = f"{path}: {len(text.splitlines())} lines"
    if suffix == ".py":
        rows = outline_py(text, depth)
    elif suffix == ".md":
        rows = outline_md(text, depth)
    elif suffix in (".yml", ".yaml"):
        rows = outline_yaml(text, depth)
    else:
        return [head]
    return [head, *cap(rows, OUTLINE_MAX - 1)]


def find_py(tree: ast.Module, name: str) -> ast.AST | None:
    node: ast.AST = tree
    for part in name.split("."):
        body = getattr(node, "body", [])
        match = next(
            (n for n in body if isinstance(n, (ast.ClassDef, *FUNCS)) and n.name == part), None
        )
        if match is None:
            if node is tree:
                for found in ast.walk(tree):
                    if isinstance(found, (ast.ClassDef, *FUNCS)) and found.name == part:
                        match = found
                        break
            if match is None:
                return None
        node = match
    return node


def section_py(text: str, name: str) -> tuple[int, int] | None:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
    node = find_py(tree, name)
    if node is None:
        return None
    decorators = getattr(node, "decorator_list", [])
    start = min([node.lineno, *(d.lineno for d in decorators)])  # type: ignore[attr-defined]
    return start, node.end_lineno  # type: ignore[attr-defined]


def section_md(text: str, wanted: str) -> tuple[int, int] | None:
    lines = text.splitlines()
    fenced = False
    start = level = 0
    for number, line in enumerate(lines, 1):
        if line.startswith("```"):
            fenced = not fenced
            continue
        match = None if fenced else HEADING.match(line)
        if not match:
            continue
        depth = len(match.group(1))
        if start and depth <= level:
            return start, number - 1
        if not start and wanted.lower() in match.group(2).lower():
            start, level = number, depth
    return (start, len(lines)) if start else None


def cmd_outline(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if not path.is_file():
        print(f"{path}: not a file")
        return 1
    print("\n".join(outline(path, args.depth)))
    return 0


def cmd_section(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if not path.is_file():
        print(f"{path}: not a file")
        return 1
    text = path.read_text(encoding="utf-8", errors="replace")
    suffix = path.suffix.lower()
    if suffix == ".py":
        span = section_py(text, args.name)
    elif suffix == ".md":
        span = section_md(text, args.name)
    else:
        print(f"{path}: section supports .py and .md")
        return 2
    if span is None:
        print(f"no match for {args.name!r}")
        return 1
    start, end = span
    lines = text.splitlines()[start - 1 : end]
    while lines and not lines[-1].strip():
        lines.pop()
    rows = [f"{start + i}: {line}" for i, line in enumerate(lines)]
    print("\n".join(cap(rows, SECTION_MAX)))
    return 0


def cmd_tasks(args: argparse.Namespace) -> int:
    result = run(["task", "--list-all", "--json"])
    if result.returncode != 0:
        print(f"task failed ({result.returncode}): {(result.stderr or '').strip()[:200]}")
        return 1
    try:
        entries = json.loads(result.stdout).get("tasks", [])
    except (json.JSONDecodeError, AttributeError):
        print("task output is not JSON")
        return 1
    pattern = re.compile(args.grep) if args.grep else None
    rows = []
    for entry in entries:
        desc = " ".join((entry.get("desc") or "").split())
        row = f"{entry.get('name', '')} - {desc}".rstrip(" -")
        if pattern is None or pattern.search(row):
            rows.append(row)
    print("\n".join(cap(rows, OUTLINE_MAX)))
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    result = run(["git", "diff", "--numstat", args.base])
    if result.returncode != 0:
        print(f"git failed ({result.returncode}): {(result.stderr or '').strip()[:200]}")
        return 1
    rows = []
    for line in result.stdout.splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        added, removed, name = parts
        rows.append(
            f"{name} +{added if added != '-' else 'bin'} -{removed if removed != '-' else 'bin'}"
        )
    print("\n".join(cap(rows, DIFF_MAX)) if rows else "no changes")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="repo_nav.py")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("outline")
    p.add_argument("path")
    p.add_argument("--depth", type=int, default=2)
    p.set_defaults(func=cmd_outline)
    p = sub.add_parser("section")
    p.add_argument("path")
    p.add_argument("name")
    p.set_defaults(func=cmd_section)
    p = sub.add_parser("tasks")
    p.add_argument("--grep")
    p.set_defaults(func=cmd_tasks)
    p = sub.add_parser("diff")
    p.add_argument("--base", default="HEAD")
    p.set_defaults(func=cmd_diff)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exit_:
        return 0 if exit_.code in (0, None) else 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
