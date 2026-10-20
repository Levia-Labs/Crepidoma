"""Lint Taskfiles against the taskfile-shell directive without a YAML library.

Checks `vars` (rules 3, 4: namespace-prefixed top-level vars in included Taskfiles, root vars
passed explicitly in `includes:`) and `shell` (rules 1, 2, 7, 9: POSIX sh in `cmds:` blocks, no
`mv -f`, no `PATH=` under `env:`, no `.venv/bin/python`, python only via `{{.PY}}` or `uv run`).

Usage: taskfile_lint.py {vars,shell,all} [--shellcheck] [--report FILE] [PATH ...]
Without PATH: every Taskfile.yml and taskfiles/**/Taskfile.yml tracked by git.
Output: `path:line: rule message`, at most 20 lines. Exit 0 clean, 1 findings, 2 usage.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

MAX_LINES = 20

KEY = re.compile(
    r"^(?P<indent>\s*)(?P<key>[A-Za-z_][\w.:-]*|'[^']*'|\"[^\"]*\")\s*:(?:\s+(?P<rest>.*))?$"
)
TEMPLATE = re.compile(r"\{\{.*?\}\}")
TEMPLATE_VAR = re.compile(r"\.([A-Za-z_]\w*)")
BLOCK_STYLE = re.compile(r"^[|>][-+0-9]*$")
KEYLIKE = re.compile(r"^[A-Za-z_]\w*:(\s|$)")

SHELL_RULES: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("rule1", re.compile(r"(^|\s)\[\[(\s|$)"), "`[[ ]]` is bash-only; use `[ ]`"),
    ("rule1", re.compile(r"<<<"), "`<<<` is bash-only; use printf and a pipe"),
    ("rule1", re.compile(r"(^|[\s;&|(])[A-Za-z_]\w*\+?=\("), "array syntax is bash-only"),
    (
        "rule1",
        re.compile(r"^\s*(function\s+\w+|declare\s+-a\b)"),
        "bash-only `function`/`declare -a`",
    ),
    ("rule9", re.compile(r"\bmv\s+(-\w*f\w*|--force)\b"), "`mv -f`; use `rm` then `mv`"),
    (
        "rule2",
        re.compile(r"\.venv/(bin|Scripts)/python"),
        "`.venv/bin/python`; use `uv run {{.PY}}`",
    ),
    (
        "rule2",
        re.compile(r"(?:^|[;&|(`]|\$\()\s*(?:exec\s+)?python3?(?=\s|$)"),
        "bare python; use `{{.PY}}` or `uv run`",
    ),
)


def run(args: list[str], text: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, input=text, capture_output=True, text=True, check=False)


def indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def is_blank(line: str) -> bool:
    stripped = line.strip()
    return not stripped or stripped.startswith("#")


def unquote(value: str) -> str:
    value = re.sub(r"\s+#.*$", "", value.strip())
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    return value


def section(lines: list[str], name: str) -> tuple[int, int] | None:
    """Half-open line range of the body of a top-level `name:` key."""
    for index, line in enumerate(lines):
        if re.match(rf"^{name}:\s*(#.*)?$", line):
            end = index + 1
            while end < len(lines) and (is_blank(lines[end]) or indent_of(lines[end]) > 0):
                end += 1
            return index + 1, end
    return None


def children(lines: list[str], start: int, end: int) -> list[int]:
    """Indices of the direct child key lines in a range."""
    body = [i for i in range(start, end) if not is_blank(lines[i])]
    if not body:
        return []
    child = min(indent_of(lines[i]) for i in body)
    return [i for i in body if indent_of(lines[i]) == child and KEY.match(lines[i])]


def top_vars(lines: list[str]) -> list[tuple[str, int]]:
    found = section(lines, "vars")
    if not found:
        return []
    return [(KEY.match(lines[i]).group("key"), i + 1) for i in children(lines, *found)]  # type: ignore[union-attr]


def all_var_names(lines: list[str]) -> set[str]:
    """Every key declared under any `vars:` or `env:` mapping, at any depth."""
    names: set[str] = set()
    for index, line in enumerate(lines):
        match = KEY.match(line)
        if not match or match.group("key") not in {"vars", "env"}:
            continue
        rest = match.group("rest") or ""
        if rest.startswith("{"):
            names.update(re.findall(r"([A-Za-z_]\w*)\s*:", rest))
            continue
        end = index + 1
        while end < len(lines) and (
            is_blank(lines[end]) or indent_of(lines[end]) > indent_of(line)
        ):
            end += 1
        names.update(KEY.match(lines[i]).group("key") for i in children(lines, index + 1, end))  # type: ignore[union-attr]
    return names


class Include:
    def __init__(self, ns: str, line: int, taskfile: str, passed: set[str]) -> None:
        self.ns, self.line, self.taskfile, self.passed = ns, line, taskfile, passed


def includes(lines: list[str]) -> list[Include]:
    found = section(lines, "includes")
    if not found:
        return []
    heads = children(lines, *found)
    result: list[Include] = []
    for n, head in enumerate(heads):
        end = heads[n + 1] if n + 1 < len(heads) else found[1]
        match = KEY.match(lines[head])
        ns = unquote(match.group("key"))  # type: ignore[union-attr]
        rest = (match.group("rest") or "").strip()  # type: ignore[union-attr]
        taskfile, passed = "", set()
        if rest.startswith("{"):
            if m := re.search(r"taskfile:\s*([^,}]+)", rest):
                taskfile = unquote(m.group(1))
            if m := re.search(r"vars:\s*\{([^}]*)\}", rest):
                passed = set(re.findall(r"([A-Za-z_]\w*)\s*:", m.group(1)))
        elif rest and not rest.startswith("#"):
            taskfile = unquote(rest)
        else:
            for i in children(lines, head + 1, end):
                sub = KEY.match(lines[i])
                key, value = sub.group("key"), (sub.group("rest") or "").strip()  # type: ignore[union-attr]
                if key == "taskfile":
                    taskfile = unquote(value)
                elif key == "vars":
                    if value.startswith("{"):
                        passed = set(re.findall(r"([A-Za-z_]\w*)\s*:", value))
                    else:
                        stop = i + 1
                        while stop < end and (
                            is_blank(lines[stop]) or indent_of(lines[stop]) > indent_of(lines[i])
                        ):
                            stop += 1
                        passed = {
                            KEY.match(lines[k]).group("key") for k in children(lines, i + 1, stop)
                        }  # type: ignore[union-attr]
        result.append(Include(ns, head + 1, taskfile, passed))
    return result


def cmd_blocks(lines: list[str]) -> list[list[tuple[int, str]]]:
    """Shell bodies under `cmds:` as lists of (line number, text)."""
    blocks: list[list[tuple[int, str]]] = []
    i = 0
    while i < len(lines):
        head = KEY.match(lines[i])
        if not head or head.group("key") != "cmds" or (head.group("rest") or "").strip():
            i += 1
            continue
        base = indent_of(lines[i])
        end = i + 1
        while end < len(lines):
            line = lines[end]
            if not is_blank(line) and (
                indent_of(line) < base
                or (indent_of(line) == base and not line.lstrip().startswith("-"))
            ):
                break
            end += 1
        j = i + 1
        while j < end:
            line = lines[j]
            dash = re.match(r"^(\s*)-\s+(.*)$", line)
            cmd = re.match(r"^(\s*)(?:-\s+)?cmd:\s*(.*)$", line)
            if is_blank(line) or not (dash or cmd):
                j += 1
                continue
            if cmd:
                rest, floor = (
                    cmd.group(2).strip(),
                    indent_of(line) if not dash else len(dash.group(1)),
                )
            else:
                rest, floor = dash.group(2).strip(), len(dash.group(1))  # type: ignore[union-attr]
                if KEYLIKE.match(rest):
                    j += 1
                    continue
            if BLOCK_STYLE.match(rest):
                body: list[tuple[int, str]] = []
                j += 1
                while j < end and (not lines[j].strip() or indent_of(lines[j]) > floor):
                    body.append((j + 1, lines[j]))
                    j += 1
                while body and not body[-1][1].strip():
                    body.pop()
                if body:
                    margin = indent_of(body[0][1])
                    blocks.append([(n, t[margin:]) for n, t in body])
            else:
                if rest and not rest.startswith("#"):
                    blocks.append([(j + 1, unquote(rest))])
                j += 1
        i = end
    return blocks


def env_path_lines(lines: list[str]) -> list[int]:
    found: list[int] = []
    for index, line in enumerate(lines):
        match = KEY.match(line)
        if not match or match.group("key") != "env":
            continue
        rest = match.group("rest") or ""
        if rest.startswith("{") and re.search(r"\bPATH\s*:", rest):
            found.append(index + 1)
            continue
        stop = index + 1
        while stop < len(lines) and (
            is_blank(lines[stop]) or indent_of(lines[stop]) > indent_of(line)
        ):
            if re.match(r"^\s+PATH\s*:", lines[stop]):
                found.append(stop + 1)
            stop += 1
    return found


def display(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def read(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def check_vars(path: Path) -> set[str]:
    findings: set[str] = set()
    lines = read(path)
    root_vars = {name for name, _ in top_vars(lines)}
    for inc in includes(lines):
        if not inc.taskfile or "{{" in inc.taskfile:
            continue
        target = path.parent / inc.taskfile
        if target.is_dir():
            target = target / "Taskfile.yml"
        if not target.is_file():
            continue
        tlines = read(target)
        prefix = re.sub(r"[^A-Za-z0-9]+", "_", inc.ns).upper() + "_"
        for name, line in top_vars(tlines):
            if not name.startswith(prefix) and name not in inc.passed:
                findings.add(
                    f"{display(target)}:{line}: rule4 top-level var {name} lacks prefix {prefix}"
                )
        used = {n for t in TEMPLATE.findall("\n".join(tlines)) for n in TEMPLATE_VAR.findall(t)}
        inherited = sorted((used & root_vars) - all_var_names(tlines) - inc.passed)
        if inherited:
            findings.add(
                f"{display(path)}:{inc.line}: rule3 include {inc.ns} inherits "
                f"{', '.join(inherited)}; pass in vars:"
            )
    return findings


def check_shell(path: Path, shellcheck: bool) -> set[str]:
    findings: set[str] = set()
    lines = read(path)
    shown = display(path)
    for line in env_path_lines(lines):
        findings.add(f"{shown}:{line}: rule7 PATH under env: is ignored by the runner")
    can_check = shellcheck and shutil.which("shellcheck") is not None
    for block in cmd_blocks(lines):
        for number, text in block:
            clean = TEMPLATE.sub("TASKVAR", text)
            if clean.lstrip().startswith("#"):
                continue
            for rule, pattern, message in SHELL_RULES:
                if pattern.search(clean):
                    findings.add(f"{shown}:{number}: {rule} {message}")
        if can_check:
            script = "\n".join(TEMPLATE.sub("TASKVAR", t) for _, t in block) + "\n"
            done = run(["shellcheck", "-s", "sh", "-f", "gcc", "-"], script)
            for row in done.stdout.splitlines():
                m = re.match(r"^[^:]*:(\d+):\d+: (.*)$", row)
                if m and 1 <= int(m.group(1)) <= len(block):
                    findings.add(
                        f"{shown}:{block[int(m.group(1)) - 1][0]}: shellcheck {m.group(2)}"
                    )
    return findings


def tracked(root: Path) -> list[Path]:
    done = subprocess.run(
        ["git", "ls-files", "Taskfile.yml", "taskfiles"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    names = (
        done.stdout.splitlines()
        if done.returncode == 0
        else [p.relative_to(root).as_posix() for p in root.rglob("Taskfile.yml")]
    )
    return [
        root / n
        for n in names
        if n == "Taskfile.yml" or (n.startswith("taskfiles/") and n.endswith("/Taskfile.yml"))
    ]


def sort_key(finding: str) -> tuple[str, int, str]:
    match = re.match(r"^(.*?):(\d+): (.*)$", finding)
    return (match.group(1), int(match.group(2)), match.group(3)) if match else (finding, 0, "")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Lint Taskfiles against the taskfile-shell directive."
    )
    parser.add_argument("check", choices=("vars", "shell", "all"))
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument(
        "--shellcheck", action="store_true", help="pipe each block to shellcheck -s sh"
    )
    parser.add_argument("--report", type=Path, help="write all findings to FILE")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exit_:
        return int(exit_.code or 0)

    paths = args.paths or tracked(Path.cwd())
    findings: set[str] = set()
    for path in paths:
        if not path.is_file():
            print(f"{path}:0: error not a file")
            return 2
        if args.check in ("vars", "all"):
            findings |= check_vars(path)
        if args.check in ("shell", "all"):
            findings |= check_shell(path, args.shellcheck)

    ordered = sorted(findings, key=sort_key)
    if args.report:
        args.report.write_text(
            "\n".join(ordered) + ("\n" if ordered else ""), encoding="utf-8", newline="\n"
        )
    shown = ordered if len(ordered) <= MAX_LINES else ordered[: MAX_LINES - 1]
    for finding in shown:
        print(finding)
    if len(ordered) > len(shown):
        print(f"... {len(ordered) - len(shown)} more (use --report FILE)")
    return 1 if ordered else 0


if __name__ == "__main__":
    sys.exit(main())
