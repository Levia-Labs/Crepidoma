#!/usr/bin/env python3
"""Docs consistency gate: broken links and README file lists, with a ratchet baseline.

Usage: docs_gate.py links|readme|all [paths...] [--update] [--baseline FILE]

Targets resolve against tracked files (`git ls-files`); a link to an untracked or ignored
path is `untracked-link`: use a code span instead. Without git, the working tree is used.
`links`: relative Markdown links and backticked repo paths that do not exist (case-exact).
`readme`: a folder README that lists files must match the folder's files (missing, extra).
Findings are `path:line: rule`. Those in `.ratchet/docs.baseline` are allowed; a new one exits 1.
`--update` rewrites the baseline. Without paths, tracked `*.md` files are checked.
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd())
BASELINE = ".ratchet/docs.baseline"
MAX_LINES = 20
SKIP = ("node_modules/", "graphify-out/", ".claude/marketplace/", "docs/superpowers/", ".venv/")
# graphify-out/ is the shared graph tasks' output; pillars name its files in prose.
GENERATED = ("build/", "dist/", "reports/", ".ratchet/", "graphify-out/")
SUFFIXES = (
    ".py", ".md", ".yml", ".yaml", ".json", ".toml", ".sh", ".txt", ".cfg",
    ".ts", ".tsx", ".js", ".css", ".html", ".baseline",
)  # fmt: skip
UNLISTED_OK = {"README.md", "__init__.py", ".gitkeep", ".DS_Store"}
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
SPAN = re.compile(r"`([^`\n]+)`")
NOT_PATH = re.compile(r"[*?<>{}|$'\"\s]|\.\.\.")
BULLET = re.compile(r"^\s*(?:[-*]|\|)\s*`([A-Za-z0-9_.\-]+)`")


def run(*command: str) -> str:
    try:
        done = subprocess.run(
            command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False
        )
    except OSError:
        return ""
    return done.stdout if done.returncode == 0 else ""


def documents(paths: list[str]) -> list[str]:
    found = paths or run("git", "ls-files", "*.md").splitlines()
    names = [p.replace("\\", "/") for p in found if p.strip()]
    return sorted(n for n in names if not n.startswith(SKIP) and (ROOT / n).is_file())


TRACKED: set[str] | None = None


def load_tracked() -> None:
    """Index tracked files and their parent dirs; None (no git) falls back to the working tree."""
    global TRACKED
    names = [n.replace("\\", "/") for n in run("git", "ls-files").splitlines() if n.strip()]
    TRACKED = set(names)
    for name in names:
        TRACKED.update(p.as_posix() for p in Path(name).parents if p.as_posix() != ".")
    TRACKED = TRACKED or None


def exists_exact(relative: str) -> bool:
    if TRACKED is not None:
        return os.path.normpath(relative).replace("\\", "/").strip("/") in TRACKED
    return exists_on_disk(relative)


def exists_on_disk(relative: str) -> bool:
    """Walk components against real directory listings; Path.exists() ignores case on Windows."""
    current = ROOT
    for part in os.path.normpath(relative).replace("\\", "/").split("/"):
        if part in ("", "."):
            continue
        try:
            names = {entry.name for entry in current.iterdir()}
        except OSError:
            return False
        if part not in names:
            return False
        current = current / part
    return True


def resolves(target: str, document: str) -> str:
    """Return "" when tracked, "untracked" when only on disk, "missing" otherwise."""
    target = target.split("#")[0].split("?")[0]
    if not target:
        return ""
    if target.startswith("/"):
        options = [target.lstrip("/")]
    else:
        options = [(Path(document).parent / target).as_posix(), target]
    if any(exists_exact(o) for o in options):
        return ""
    if TRACKED is not None and any(exists_on_disk(o) for o in options):
        return "untracked"
    return "missing"


def is_path_claim(token: str) -> bool:
    if NOT_PATH.search(token) or token.startswith(("http", "#", "mailto:", "~", "/", "-")):
        return False
    if token.startswith(GENERATED) or "/" not in token:
        return False
    return token.endswith(SUFFIXES) or token.endswith("/")


def body_lines(text: str):
    fenced = False
    for number, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
        elif not fenced:
            yield number, line


def check_links(document: str) -> list[str]:
    text = (ROOT / document).read_text(encoding="utf-8", errors="replace")
    found = []
    for number, line in body_lines(text):
        targets = [t for t in LINK.findall(line) if not t.startswith(("http", "#", "mailto:"))]
        spans = [s.strip() for s in SPAN.findall(LINK.sub(" ", line)) if is_path_claim(s.strip())]
        for target in targets + spans:
            if NOT_PATH.search(target) or target.startswith(GENERATED):
                continue
            state = resolves(target, document)
            if state == "untracked":
                found.append(f"{document}:{number}: untracked-link {target}")
            elif state:
                found.append(f"{document}:{number}: links {target}")
    return found


def check_readme(document: str) -> list[str]:
    if Path(document).name != "README.md":
        return []
    text = (ROOT / document).read_text(encoding="utf-8", errors="replace")
    listed: dict[str, int] = {}
    for number, line in body_lines(text):
        if match := BULLET.match(line):
            listed.setdefault(match.group(1), number)
    if not listed:
        return []
    folder = (ROOT / document).parent
    if TRACKED is not None:
        here = Path(document).parent.as_posix()
        names = {Path(t).name for t in TRACKED if Path(t).parent.as_posix() == here}
        actual = {n for n in names if (folder / n).is_file() and n not in UNLISTED_OK}
    else:
        actual = {p.name for p in folder.iterdir() if p.is_file() and p.name not in UNLISTED_OK}
    actual = {n for n in actual if not n.endswith(".meta")}
    found = [
        f"{document}:{n}: readme extra {name}"
        for name, n in listed.items()
        if name not in actual and not name.endswith(".meta")
    ]
    found += [f"{document}:1: readme missing {name}" for name in actual - set(listed)]
    return found


def read_baseline(path: Path) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


def rule_kind(finding: str) -> str:
    return finding.split(": ", 1)[1].split(" ", 1)[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="docs_gate", description=__doc__.splitlines()[0])
    parser.add_argument("check", choices=("links", "readme", "all"))
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--update", action="store_true")
    parser.add_argument("--baseline", default=BASELINE)
    args = parser.parse_args(argv)

    kinds = ("links", "readme") if args.check == "all" else (args.check,)
    load_tracked()
    docs = documents(args.paths)
    findings: list[str] = []
    for document in docs:
        if "links" in kinds:
            findings += check_links(document)
        if "readme" in kinds:
            findings += check_readme(document)
    findings = sorted(set(findings))

    baseline_path = ROOT / args.baseline
    known = read_baseline(baseline_path)
    if args.update:
        keep = [k for k in known if rule_kind(k) not in kinds] if not args.paths else known
        merged = sorted(set(keep) | set(findings)) if args.paths else sorted(set(keep + findings))
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        with baseline_path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.writelines(f"{line}\n" for line in merged)
        print(f"baseline {args.baseline}: {len(merged)} findings")
        return 0

    new = [f for f in findings if f not in set(known)]
    shown = new[: MAX_LINES - 1]
    for line in shown:
        print(line)
    print(f"{len(new)} new, {len(findings) - len(new)} baselined, {len(docs)} files")
    return 1 if new else 0


if __name__ == "__main__":
    sys.exit(main())
