# Crepidoma Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn Crepidoma into the public foundation repo that pillar projects link (plugin marketplace, git submodule, pre-commit remote) instead of copying LLM directives, agents, hooks, gates, configs, Taskfiles and process ADRs.

**Architecture:** One repo, three consumption surfaces: a Claude Code plugin marketplace (`crepidoma-core`: directives injected at SessionStart, agents, PreToolUse guard, `digest` binary), a git submodule (`taskfiles/`, `configs/`), and a pre-commit hook repo (`.pre-commit-hooks.yaml` backed by `tools/`). Crepidoma gates itself with the same tools first; drifted pillar copies are merged into supersets by a named merge agent.

**Tech Stack:** Python 3.12+ stdlib for all scripts, uv, pytest, ruff, pre-commit, Task (taskfile.dev v3), prettier, yamllint, shellcheck, gitleaks, actionlint, zizmor, ast-grep, semgrep and osv-scanner (CI), Claude Code plugin system.

**Spec:** `docs/superpowers/specs/2026-10-20-crepidoma-foundation-design.md`

## Global Constraints

1. No secret, credential, email, absolute local path or private repo name in any committed file. `tools/scrub_check.py` enforces; it runs on every commit and push.
2. Pillar repo names, local paths and merge provenance live only in gitignored `.local/` and `.scrub-denylist`. Public docs say "pillar repos". This overrides spec 2.4's committed `merge-conflicts.md` path: conflicts go to `.local/merge-conflicts.md`.
3. `PILLARS` = directory holding the pillar checkouts, default `..` (Crepidoma's parent). Never write its absolute value into a committed file.
4. Scripts: Python `>=3.12`, standard library only, `main(argv: list[str] | None = None) -> int`.
5. Hook and binary launchers call `uv run --no-project --quiet python "<path>"`, with `${CLAUDE_PLUGIN_ROOT}` paths double-quoted.
6. Directive context cap: 10,000 characters total (`LIMIT = 10_000`).
7. Long-file ratchet threshold: 400 lines.
8. Third-party plugins and skills are referenced, never copied.
9. Work on branch `foundation`. No push and no PR without explicit user confirmation at Task 19. The remote is public.
10. Deviation from spec 6.2, recorded: semgrep and osv-scanner run in CI only (no native Windows support for semgrep); pip-audit/npm audit are covered by osv-scanner in Crepidoma and offered to pillars in `templates/`.
11. Subagents: named single-job agents only (`merge-curator` defined in Task 0, `feature-dev:code-reviewer` for review). Receipts at most 10 lines.
12. Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. Plugin installed under a path containing spaces: hook commands must still resolve their scripts (Task 6 test asserts quoting and existence).
2. Malformed or empty JSON on hook stdin: guard and injector must exit 0 and never block the session (Tasks 6 and 7 tests).
3. Directive set growing past 10,000 characters: build test fails before release; runtime truncates with a visible notice (Tasks 7 and 8 tests).
4. CRLF checkouts on Windows: drift comparison must treat CRLF and LF copies as identical; scrub must report correct line numbers (Tasks 1 and 12 tests).
5. Denylisted names that are also common words, plus git SSH URLs and bot emails: scrub needs an inline `scrub:allow` escape and an email allowlist (Task 1 tests).

---

### Task 0: Branch, scaffold, merge agent

**Files:**

- Modify: `.gitignore`
- Create: `pyproject.toml`, `.scrub-denylist.example`, `.claude/agents/merge-curator.md`, `CHANGELOG.md`

**Interfaces:**

- Produces: uv project with dev group (`pytest`, `ruff`, `pre-commit`); pytest `pythonpath` makes `tools/*.py` and `plugins/crepidoma-core/scripts/*.py` importable by module name; agent `merge-curator`.

- [ ] **Step 1: Create branch**

Run: `git switch -c foundation`
Expected: `Switched to a new branch 'foundation'`

- [ ] **Step 2: Append to `.gitignore`**

```gitignore
# Crepidoma local-only data
.local/
.scrub-denylist
.claude/settings.local.json
.credentials.json
*.key
*.pem
node_modules/
```

- [ ] **Step 3: Write `pyproject.toml`**

```toml
[project]
name = "crepidoma"
version = "0.1.0"
description = "LLM tooling foundation for Levia Labs pillar projects"
requires-python = ">=3.12"
license = "MIT"
dependencies = []

[project.scripts]
crepidoma-scrub = "scrub_check:main"
crepidoma-ratchet = "ratchet:main"
crepidoma-drift = "drift_check:main"

[build-system]
requires = ["hatchling>=1.25"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
only-include = ["tools"]
sources = ["tools"]

[dependency-groups]
dev = ["pytest>=8", "ruff>=0.6", "pre-commit>=4"]

[tool.uv]
package = false  # uv does not build the project locally; pre-commit try-repo and pillars do

[tool.pytest.ini_options]
testpaths = ["tests", "plugins/crepidoma-core/tests"]
pythonpath = ["tools", "plugins/crepidoma-core/scripts"]
addopts = "--import-mode=importlib -q"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP", "SIM"]
```

- [ ] **Step 4: Write `.scrub-denylist.example`**

```text
# One private name per line, matched case-insensitively on word boundaries.
# Generate the real list with: task scrub:denylist
# The real file is .scrub-denylist and is gitignored.
```

- [ ] **Step 5: Write `CHANGELOG.md`**

```markdown
# Changelog
```

- [ ] **Step 6: Write `.claude/agents/merge-curator.md`**

```markdown
---
name: merge-curator
description: Merges drifted copies of one file family from pillar checkouts into one Crepidoma superset. Single job per call. Use only for the merge tasks of the foundation plan.
tools: Read, Grep, Glob, Bash, Write, Edit
model: opus
---

Input from the caller: family name, source globs relative to the PILLARS directory, target paths, family rules.

1. Enumerate sources with Glob under PILLARS (default `..`, skip `Crepidoma`). Append `sha256  repo/path` per source to `.local/merge-log/<family>.md`.
2. Group sources by role or section. Union all rules. Drop exact and near duplicates. On conflicting rules keep the stricter wording and log both variants, with source repo names, under `## <family>` in `.local/merge-conflicts.md`.
3. Leave out content that names a specific pillar, product, customer, person, absolute path or private URL. Log each exclusion with its source to `.local/repo-local.md`.
4. Record every alias (old file name to new target) in `.local/merge-log/<family>.md`.
5. Write the targets. Run `uv run python tools/scrub_check.py <targets>` and `uv run pytest`. Fix hits until both pass.
6. Return a receipt of at most 10 lines: targets written, conflicts logged, exclusions logged, test and scrub results. Never return file contents.
```

- [ ] **Step 7: Sync and commit**

Run: `uv sync`
Expected: creates `.venv` and `uv.lock`, exit 0.

```bash
git add .gitignore pyproject.toml uv.lock .scrub-denylist.example CHANGELOG.md .claude/agents/merge-curator.md
git commit -m "chore: scaffold uv project and merge-curator agent"
```

---

### Task 1: scrub_check

**Files:**

- Create: `tools/scrub_check.py`
- Test: `tests/test_scrub_check.py`

**Interfaces:**

- Produces: `RULES: dict[str, re.Pattern[str]]`, `allowed_email(address: str) -> bool`, `load_denylist(path: Path | None) -> re.Pattern[str] | None`, `scan_text(text: str, deny: re.Pattern[str] | None) -> list[tuple[int, str]]`, `scan_file(path: Path, deny) -> list[tuple[int, str]]`, `main(argv) -> int` (CLI: `[--denylist FILE] PATH...`, prints `path:line: rule`, exit 1 on any hit).

- [ ] **Step 1: Write the failing tests**

Fixtures are built by concatenation so this file never trips the scrub or gitleaks itself.

```python
from pathlib import Path

import scrub_check

DRIVE = "C" + ":"
PROJECTS = "X" + ":/Projects/thing"


def test_clean_text_has_no_hits():
    assert scrub_check.scan_text("plain words\nmore words\n", None) == []


def test_windows_user_path_hit():
    text = f"see {DRIVE}\\Users\\someone\\notes\n"
    assert scrub_check.scan_text(text, None) == [(1, "windows-user-path")]


def test_projects_drive_path_hit():
    assert scrub_check.scan_text(PROJECTS + "\n", None) == [(1, "local-projects-path")]


def test_posix_home_hit_but_not_url_or_tilde():
    home = "/ho" + "me/someone/x"
    assert scrub_check.scan_text(f"cd {home}\n", None) == [(1, "posix-home-path")]
    assert scrub_check.scan_text("see https://example.com/Users/x and ~/.claude\n", None) == []


def test_email_hit_and_allowlist():
    addr = "someone" + "@" + "corp.io"
    assert scrub_check.scan_text(f"mail {addr}\n", None) == [(1, "email")]
    bot = "noreply" + "@" + "anthropic.com"
    ssh = "git" + "@" + "github.com:Org/Repo.git"
    assert scrub_check.scan_text(f"by <{bot}> via {ssh}\n", None) == []


def test_token_hit():
    token = "gh" + "p_" + "a" * 36
    assert scrub_check.scan_text(f"t={token}\n", None) == [(1, "token")]


def test_denylist_word_boundary(tmp_path: Path):
    deny_file = tmp_path / "deny"
    deny_file.write_text("# comment\nsecretproj\n", encoding="utf-8")
    deny = scrub_check.load_denylist(deny_file)
    assert scrub_check.scan_text("about SecretProj today\n", deny) == [(1, "denylisted-name")]
    assert scrub_check.scan_text("secretprojects\n", deny) == []


def test_allow_marker_skips_line():
    assert scrub_check.scan_text(PROJECTS + "  scrub" + ":allow\n", None) == []


def test_missing_or_empty_denylist_is_none(tmp_path: Path):
    assert scrub_check.load_denylist(tmp_path / "absent") is None
    empty = tmp_path / "empty"
    empty.write_text("# only comments\n", encoding="utf-8")
    assert scrub_check.load_denylist(empty) is None


def test_binary_file_skipped(tmp_path: Path):
    blob = tmp_path / "blob.bin"
    blob.write_bytes(b"\xff\xfe\x00\x81")
    assert scrub_check.scan_file(blob, None) == []


def test_crlf_line_numbers(tmp_path: Path):
    target = tmp_path / "a.txt"
    target.write_bytes(b"ok\r\n" + (PROJECTS + "\r\n").encode())
    assert scrub_check.scan_file(target, None) == [(2, "local-projects-path")]


def test_main_exit_codes(tmp_path: Path, capsys):
    clean = tmp_path / "clean.md"
    clean.write_text("fine\n", encoding="utf-8")
    dirty = tmp_path / "dirty.md"
    dirty.write_text(PROJECTS + "\n", encoding="utf-8")
    none = str(tmp_path / "none")
    assert scrub_check.main(["--denylist", none, str(clean)]) == 0
    assert scrub_check.main(["--denylist", none, str(dirty)]) == 1
    assert "dirty.md:1: local-projects-path" in capsys.readouterr().out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_scrub_check.py`
Expected: FAIL, `ModuleNotFoundError: No module named 'scrub_check'`

- [ ] **Step 3: Implement `tools/scrub_check.py`**

```python
"""Fail when files carry local paths, emails, tokens or denylisted names.

Usage: scrub_check.py [--denylist FILE] PATH...
Prints `path:line: rule` per hit; exit 1 on any hit, 0 when clean.
A line containing `scrub:allow` is skipped. Undecodable files are skipped.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

RULES: dict[str, re.Pattern[str]] = {
    "windows-user-path": re.compile(r"\b[A-Za-z]:[\\/]+Users[\\/]+\w", re.IGNORECASE),
    "local-projects-path": re.compile(r"\b[A-Za-z]:[\\/]+Projects\b", re.IGNORECASE),
    "posix-home-path": re.compile(r"(?<![\w.~])/(?:home|Users)/\w"),
    "email": re.compile(r"\b[\w.%+-]+@[\w-]+(?:\.[\w-]+)*\.[A-Za-z]{2,}\b"),
    "token": re.compile(
        r"sk-ant-[\w-]{20,}|gh[pousr]_\w{30,}|github_pat_\w{30,}|AKIA[0-9A-Z]{16}"
        r"|-----BEGIN [A-Z ]*PRIVATE KEY-----"
    ),
}
ALLOWED_EMAILS = {"noreply@anthropic.com", "git@github.com"}
ALLOWED_EMAIL_SUFFIXES = ("@users.noreply.github.com", "@example.com")
ALLOW_MARKER = "scrub:allow"


def allowed_email(address: str) -> bool:
    address = address.lower()
    return address in ALLOWED_EMAILS or address.endswith(ALLOWED_EMAIL_SUFFIXES)


def load_denylist(path: Path | None) -> re.Pattern[str] | None:
    if path is None or not path.is_file():
        return None
    words = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    words = [word for word in words if word and not word.startswith("#")]
    if not words:
        return None
    return re.compile(r"\b(?:" + "|".join(map(re.escape, words)) + r")\b", re.IGNORECASE)


def scan_text(text: str, deny: re.Pattern[str] | None) -> list[tuple[int, str]]:
    hits: list[tuple[int, str]] = []
    for number, line in enumerate(text.splitlines(), 1):
        if ALLOW_MARKER in line:
            continue
        for rule, pattern in RULES.items():
            matches = [m.group() for m in pattern.finditer(line)]
            if rule == "email":
                matches = [m for m in matches if not allowed_email(m)]
            if matches:
                hits.append((number, rule))
        if deny is not None and deny.search(line):
            hits.append((number, "denylisted-name"))
    return hits


def scan_file(path: Path, deny: re.Pattern[str] | None) -> list[tuple[int, str]]:
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    return scan_text(text, deny)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--denylist", type=Path, default=Path(".scrub-denylist"))
    parser.add_argument("paths", nargs="*", type=Path)
    args = parser.parse_args(argv)
    deny = load_denylist(args.denylist)
    found = 0
    for path in args.paths:
        if not path.is_file():
            continue
        for number, rule in scan_file(path, deny):
            print(f"{path.as_posix()}:{number}: {rule}")
            found += 1
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_scrub_check.py`
Expected: `12 passed`

- [ ] **Step 5: Scrub the repo so far**

Run: `uv run python tools/scrub_check.py $(git ls-files) tools/scrub_check.py tests/test_scrub_check.py`
Expected: no output, exit 0. Any hit in the spec or plan gets rewritten, not allow-marked.

- [ ] **Step 6: Commit**

```bash
git add tools/scrub_check.py tests/test_scrub_check.py
git commit -m "feat(tools): add scrub_check publication guard"
```

---

### Task 2: ratchet

**Files:**

- Create: `tools/ratchet.py`
- Test: `tests/test_ratchet.py`

**Interfaces:**

- Produces: `long_files(files: list[str], baseline: Path, max_lines: int, update: bool) -> int`, `metric(baseline: Path, value: float, direction: str, update: bool) -> int`, `main(argv) -> int` (CLI subcommands `long-files [--baseline F] [--max-lines N] [--update] [--git] FILES...` and `metric --baseline F --value X --direction up|down [--update]`). Baseline format for long files: `posix-path<TAB>lines` per line.

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path

import ratchet


def write(path: Path, lines: int) -> None:
    path.write_text("x\n" * lines, encoding="utf-8")


def test_new_long_file_fails(tmp_path: Path, capsys):
    big = tmp_path / "big.py"
    write(big, 5)
    assert ratchet.long_files([str(big)], tmp_path / "b", max_lines=3, update=False) == 1
    assert "new long file" in capsys.readouterr().out


def test_baselined_file_may_shrink_not_grow(tmp_path: Path):
    big = tmp_path / "big.py"
    base = tmp_path / "long.baseline"
    write(big, 5)
    assert ratchet.long_files([str(big)], base, 3, update=True) == 0
    write(big, 4)
    assert ratchet.long_files([str(big)], base, 3, update=False) == 0
    write(big, 6)
    assert ratchet.long_files([str(big)], base, 3, update=False) == 1


def test_short_and_missing_files_ignored(tmp_path: Path):
    small = tmp_path / "s.py"
    write(small, 2)
    files = [str(small), str(tmp_path / "gone.py")]
    assert ratchet.long_files(files, tmp_path / "b", 3, update=False) == 0


def test_metric_up(tmp_path: Path):
    base = tmp_path / "coverage.baseline"
    assert ratchet.metric(base, 80.0, "up", update=False) == 0
    assert base.read_text(encoding="utf-8").strip() == "80.0"
    assert ratchet.metric(base, 79.9, "up", update=False) == 1
    assert ratchet.metric(base, 81.0, "up", update=True) == 0
    assert base.read_text(encoding="utf-8").strip() == "81.0"


def test_metric_down(tmp_path: Path):
    base = tmp_path / "duplication.baseline"
    base.write_text("5\n", encoding="utf-8")
    assert ratchet.metric(base, 6.0, "down", update=False) == 1
    assert ratchet.metric(base, 4.0, "down", update=False) == 0


def test_main_long_files(tmp_path: Path):
    big = tmp_path / "big.py"
    write(big, 5)
    args = ["long-files", "--baseline", str(tmp_path / "b"), "--max-lines", "3", str(big)]
    assert ratchet.main(args) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ratchet.py`
Expected: FAIL, `ModuleNotFoundError: No module named 'ratchet'`

- [ ] **Step 3: Implement `tools/ratchet.py`**

```python
"""Ratchet quality metrics so they never get worse.

long-files: files over --max-lines must be in the baseline and may not grow.
metric: one number compared with a baseline value; --direction says which way is better.
A missing metric baseline is created from the first value.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def count_lines(path: Path) -> int:
    with path.open("rb") as handle:
        return sum(1 for _ in handle)


def read_baseline(path: Path) -> dict[str, int]:
    if not path.is_file():
        return {}
    entries: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        name, _, value = line.rpartition("\t")
        entries[name] = int(value)
    return entries


def write_baseline(path: Path, entries: dict[str, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(f"{name}\t{lines}\n" for name, lines in sorted(entries.items()))
    path.write_text(body, encoding="utf-8")


def long_files(files: list[str], baseline: Path, max_lines: int, update: bool) -> int:
    current: dict[str, int] = {}
    for name in files:
        path = Path(name)
        if path.is_file():
            lines = count_lines(path)
            if lines > max_lines:
                current[path.as_posix()] = lines
    if update:
        write_baseline(baseline, current)
        print(f"baseline: {len(current)} long files")
        return 0
    allowed = read_baseline(baseline)
    failures = []
    for name, lines in sorted(current.items()):
        limit = allowed.get(name)
        if limit is None:
            failures.append(f"{name}: {lines} lines > {max_lines} (new long file)")
        elif lines > limit:
            failures.append(f"{name}: {lines} lines > baseline {limit}")
    for failure in failures:
        print(failure)
    return 1 if failures else 0


def metric(baseline: Path, value: float, direction: str, update: bool) -> int:
    text = baseline.read_text(encoding="utf-8").strip() if baseline.is_file() else ""
    if not text:
        baseline.parent.mkdir(parents=True, exist_ok=True)
        baseline.write_text(f"{value}\n", encoding="utf-8")
        print(f"baseline set: {value}")
        return 0
    base = float(text)
    worse = value < base if direction == "up" else value > base
    if worse:
        print(f"{value} is worse than baseline {base} ({direction} is better)")
        return 1
    if update and value != base:
        baseline.write_text(f"{value}\n", encoding="utf-8")
        print(f"baseline improved: {base} -> {value}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    files_parser = sub.add_parser("long-files")
    files_parser.add_argument("--baseline", type=Path, default=Path(".ratchet/long-files.baseline"))
    files_parser.add_argument("--max-lines", type=int, default=400)
    files_parser.add_argument("--update", action="store_true")
    files_parser.add_argument("--git", action="store_true", help="check every tracked file")
    files_parser.add_argument("files", nargs="*")
    metric_parser = sub.add_parser("metric")
    metric_parser.add_argument("--baseline", type=Path, required=True)
    metric_parser.add_argument("--value", type=float, required=True)
    metric_parser.add_argument("--direction", choices=["up", "down"], required=True)
    metric_parser.add_argument("--update", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "metric":
        return metric(args.baseline, args.value, args.direction, args.update)
    files = args.files
    if args.git:
        listing = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True)
        files = listing.stdout.splitlines()
    return long_files(files, args.baseline, args.max_lines, args.update)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ratchet.py`
Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add tools/ratchet.py tests/test_ratchet.py
git commit -m "feat(tools): add long-file and metric ratchet"
```

---

### Task 3: Commit gates and root Taskfile

**Files:**

- Create: `.pre-commit-config.yaml`, `Taskfile.yml`, `.ratchet/long-files.baseline`, `.yamllint`, `.prettierrc`, `.editorconfig`, `.gitattributes`

**Interfaces:**

- Consumes: `tools/scrub_check.py`, `tools/ratchet.py`.
- Produces: hook ids `crepidoma-scrub`, `crepidoma-long-files`, `pytest`, `plugin-validate`; tasks `setup`, `fmt`, `lint`, `sec`, `test`, `plugin:validate`, `ratchet:update`, `hooks:pre-commit`, `hooks:pre-push`, `validate`. Later tasks add `scrub:denylist`, `drift`, `release`.

- [ ] **Step 1: Write `.editorconfig`, `.gitattributes`, `.yamllint`, `.prettierrc`**

`.editorconfig`:

```ini
root = true

[*]
charset = utf-8
end_of_line = lf
indent_style = space
indent_size = 2
insert_final_newline = true
trim_trailing_whitespace = true

[*.py]
indent_size = 4

[*.md]
trim_trailing_whitespace = false
```

`.gitattributes`:

```gitattributes
* text=auto eol=lf
*.cmd text eol=crlf
*.svg binary
```

`.yamllint`:

```yaml
extends: default
rules:
  line-length: { max: 120 }
  document-start: disable
  truthy: { check-keys: false }
```

`.prettierrc`:

```json
{ "proseWrap": "preserve", "printWidth": 100 }
```

- [ ] **Step 2: Write `.pre-commit-config.yaml`**

```yaml
default_install_hook_types: [pre-commit, pre-push]
default_stages: [pre-commit, pre-push]
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: check-yaml
      - id: check-json
      - id: check-toml
      - id: end-of-file-fixer
      - id: trailing-whitespace
      - id: mixed-line-ending
        args: [--fix=lf]
        exclude: \.cmd$
      - id: check-added-large-files
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.9
    hooks:
      - id: ruff
      - id: ruff-format
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.21.2
    hooks:
      - id: gitleaks
  - repo: https://github.com/adrienverge/yamllint
    rev: v1.35.1
    hooks:
      - id: yamllint
  - repo: https://github.com/shellcheck-py/shellcheck-py
    rev: v0.10.0.1
    hooks:
      - id: shellcheck
  - repo: https://github.com/rbubley/mirrors-prettier
    rev: v3.3.3
    hooks:
      - id: prettier
        types_or: [markdown, json, yaml, javascript]
  - repo: https://github.com/Mateusz-Grzelinski/actionlint-py
    rev: v1.7.3.17
    hooks:
      - id: actionlint
  - repo: https://github.com/woodruffw/zizmor-pre-commit
    rev: v0.9.2
    hooks:
      - id: zizmor
  - repo: local
    hooks:
      - id: crepidoma-scrub
        name: crepidoma scrub (paths, emails, tokens, private names)
        entry: uv run --no-project --quiet python tools/scrub_check.py
        language: system
        types: [text]
      - id: crepidoma-long-files
        name: crepidoma long-file ratchet
        entry: uv run --no-project --quiet python tools/ratchet.py long-files --max-lines 400
        language: system
        types: [text]
      - id: pytest
        name: pytest
        entry: uv run pytest
        language: system
        pass_filenames: false
        stages: [pre-push]
      - id: plugin-validate
        name: claude plugin validate
        entry: claude plugin validate .
        language: system
        pass_filenames: false
        stages: [pre-push]
```

- [ ] **Step 3: Pin hook revisions to latest tags**

Run: `uv run pre-commit autoupdate`
Expected: each repo line reports `updating <old> -> <new>` or `already up to date`; exit 0. A repo that moved (for example zizmor) is replaced with the redirect target shown by `gh repo view <owner>/<name> --json url`.

- [ ] **Step 4: Write `Taskfile.yml`**

```yaml
version: "3"

vars:
  PILLARS: '{{.PILLARS | default ".."}}'
  LINT_HOOKS: [ruff, yamllint, shellcheck, actionlint, zizmor, check-yaml, check-json, check-toml]
  SEC_HOOKS: [gitleaks, crepidoma-scrub]

tasks:
  setup:
    desc: Install dev dependencies and git hooks
    cmds:
      - uv sync
      - uv run pre-commit install

  fmt:
    desc: Format Python, Markdown, JSON, YAML
    cmds:
      - cmd: uv run pre-commit run ruff-format --all-files
        ignore_error: true
      - cmd: uv run pre-commit run prettier --all-files
        ignore_error: true

  lint:
    desc: Run linters over the whole repo
    cmds:
      - for: { var: LINT_HOOKS }
        cmd: uv run pre-commit run {{.ITEM}} --all-files

  sec:
    desc: Secret scan and publication scrub over the whole repo
    cmds:
      - for: { var: SEC_HOOKS }
        cmd: uv run pre-commit run {{.ITEM}} --all-files

  test:
    desc: Run pytest
    cmds:
      - uv run pytest

  plugin:validate:
    desc: Validate marketplace and plugin manifests
    cmds:
      - claude plugin validate .

  ratchet:update:
    desc: Rewrite the long-file baseline from all tracked files
    cmds:
      - uv run python tools/ratchet.py long-files --max-lines 400 --update --git

  hooks:pre-commit:
    desc: Run the pre-commit stage on all files
    cmds:
      - uv run pre-commit run --all-files --hook-stage pre-commit

  hooks:pre-push:
    desc: Run the pre-push stage on all files
    cmds:
      - uv run pre-commit run --all-files --hook-stage pre-push

  validate:
    desc: Full gate, same as CI
    cmds:
      - task: hooks:pre-push
```

- [ ] **Step 5: Create the baseline and install hooks**

Run: `task ratchet:update`
Expected: `baseline: 0 long files` (the plan file may exceed 400 lines; then `baseline: 1 long files`). File `.ratchet/long-files.baseline` exists.

Run: `task setup`
Expected: `pre-commit installed at .git/hooks/pre-commit` and `.git/hooks/pre-push`.

- [ ] **Step 6: Run the pre-commit stage and fix**

Run: `task fmt` then `task hooks:pre-commit`
Expected: every hook `Passed` or `(no files to check)Skipped`. `plugin-validate` and `pytest` do not run at this stage.

- [ ] **Step 7: Commit (hooks now active)**

```bash
git add -A
git commit -m "build: add pre-commit gates and root Taskfile"
```

Expected: hook output lists every pre-commit hook as Passed, then the commit is created.

---

### Task 4: Denylist generator

**Files:**

- Create: `tools/denylist.py`
- Test: `tests/test_denylist.py`
- Modify: `Taskfile.yml` (add `scrub:denylist`)

**Interfaces:**

- Produces: `parse_slug(url: str) -> str | None`, `remote_slug(repo: Path) -> str | None`, `is_private(slug: str) -> bool`, `collect(pillars: Path, remote=remote_slug, probe=is_private) -> list[str]`, `main(argv) -> int` (CLI: `PILLARS [--out .scrub-denylist]`).

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path

import denylist


def test_parse_slug():
    assert denylist.parse_slug("https://github.com/Org/Repo.git\n") == "Org/Repo"
    assert denylist.parse_slug("git" + "@" + "github.com:Org/Repo.git") == "Org/Repo"
    assert denylist.parse_slug("https://gitlab.com/x/y") is None


def test_collect_private_and_remote_less(tmp_path: Path):
    for name in ("alpha", "beta", "gamma"):
        (tmp_path / name).mkdir()
    (tmp_path / "file.txt").write_text("x", encoding="utf-8")
    remotes = {"alpha": "Org/alpha-repo", "beta": "Org/beta", "gamma": None}
    private = {"Org/alpha-repo": True, "Org/beta": False}
    names = denylist.collect(
        tmp_path, remote=lambda d: remotes[d.name], probe=lambda slug: private[slug]
    )
    assert names == ["alpha", "alpha-repo", "gamma"]


def test_main_writes_file(tmp_path: Path, monkeypatch):
    (tmp_path / "pillars" / "secret").mkdir(parents=True)
    out = tmp_path / "deny"
    monkeypatch.setattr(denylist, "remote_slug", lambda d: None)
    assert denylist.main([str(tmp_path / "pillars"), "--out", str(out)]) == 0
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("#")
    assert lines[1:] == ["secret"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_denylist.py`
Expected: FAIL, `ModuleNotFoundError: No module named 'denylist'`

- [ ] **Step 3: Implement `tools/denylist.py`**

```python
"""Write the scrub denylist: names of private or remote-less repos under a pillars directory.

Usage: denylist.py PILLARS [--out .scrub-denylist]
A repo whose visibility cannot be determined is treated as private.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from collections.abc import Callable
from pathlib import Path

SLUG = re.compile(r"github\.com[:/]([\w.-]+)/([\w.-]+?)(?:\.git)?/?$")


def parse_slug(url: str) -> str | None:
    match = SLUG.search(url.strip())
    return f"{match[1]}/{match[2]}" if match else None


def remote_slug(repo: Path) -> str | None:
    if not (repo / ".git").exists():
        return None
    result = subprocess.run(
        ["git", "-C", str(repo), "remote", "get-url", "origin"], capture_output=True, text=True
    )
    return parse_slug(result.stdout) if result.returncode == 0 else None


def is_private(slug: str) -> bool:
    result = subprocess.run(
        ["gh", "repo", "view", slug, "--json", "isPrivate", "-q", ".isPrivate"],
        capture_output=True,
        text=True,
    )
    return result.returncode != 0 or result.stdout.strip() == "true"


def collect(
    pillars: Path,
    remote: Callable[[Path], str | None] | None = None,
    probe: Callable[[str], bool] | None = None,
) -> list[str]:
    remote = remote or remote_slug
    probe = probe or is_private
    names: set[str] = set()
    for repo in sorted(path for path in pillars.iterdir() if path.is_dir()):
        slug = remote(repo)
        if slug is None:
            names.add(repo.name)
        elif probe(slug):
            names.update({repo.name, slug.split("/")[1]})
    return sorted(names)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pillars", type=Path)
    parser.add_argument("--out", type=Path, default=Path(".scrub-denylist"))
    args = parser.parse_args(argv)
    names = collect(args.pillars, remote=remote_slug, probe=is_private)
    header = "# generated by tools/denylist.py; gitignored, never commit\n"
    args.out.write_text(header + "".join(f"{name}\n" for name in names), encoding="utf-8")
    print(f"{len(names)} names written to {args.out.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Note: `main` passes `remote=remote_slug` by module lookup at call time so the monkeypatch in the test applies.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_denylist.py`
Expected: `3 passed`

- [ ] **Step 5: Add the task to `Taskfile.yml`** (after `sec`)

```yaml
scrub:denylist:
  desc: Generate gitignored .scrub-denylist from private repos under PILLARS
  cmds:
    - uv run python tools/denylist.py "{{.PILLARS}}" --out .scrub-denylist
```

- [ ] **Step 6: Generate and run the full scrub**

Run: `task scrub:denylist`
Expected: `<n> names written to .scrub-denylist`, `git status --short` does not list `.scrub-denylist`.

Run: `task sec`
Expected: gitleaks and crepidoma-scrub `Passed`. A hit on a common word gets `scrub:allow` on that line only; a real leak gets rewritten.

- [ ] **Step 7: Commit**

```bash
git add tools/denylist.py tests/test_denylist.py Taskfile.yml
git commit -m "feat(tools): generate scrub denylist from private pillar repos"
```

---

### Task 5: Plugin skeleton and digest

**Files:**

- Create: `.claude-plugin/marketplace.json`, `plugins/crepidoma-core/.claude-plugin/plugin.json`, `plugins/crepidoma-core/scripts/digest.py` (copied), `plugins/crepidoma-core/bin/digest`, `plugins/crepidoma-core/bin/digest.cmd`
- Test: `plugins/crepidoma-core/tests/test_digest.py`

**Interfaces:**

- Produces: marketplace `crepidoma`, plugin `crepidoma-core` version `0.1.0`; module `digest` with `MAX_LINES = 20`, `digest(text, grep, tail, max_bytes, size=None) -> str`, `main(argv) -> int`; executable `digest` on PATH inside Claude sessions.

- [ ] **Step 1: Write manifests**

`.claude-plugin/marketplace.json`:

```json
{
  "name": "crepidoma",
  "owner": { "name": "Levia Labs" },
  "metadata": { "description": "Foundation plugins for Levia Labs pillar projects" },
  "plugins": [
    {
      "name": "crepidoma-core",
      "source": "./plugins/crepidoma-core",
      "description": "Shared directives, agents, guard hooks and output tools"
    }
  ]
}
```

`plugins/crepidoma-core/.claude-plugin/plugin.json`:

```json
{
  "name": "crepidoma-core",
  "version": "0.1.0",
  "description": "Shared directives, agents, guard hooks and output tools for Levia Labs pillar projects",
  "author": { "name": "Levia Labs" },
  "license": "MIT",
  "repository": "https://github.com/Levia-Labs/Crepidoma"
}
```

- [ ] **Step 2: Copy digest verbatim**

Run: `mkdir -p plugins/crepidoma-core/scripts && cp ~/.claude/bin/digest.py plugins/crepidoma-core/scripts/digest.py`
Expected: exit 0.

- [ ] **Step 3: Write characterization tests**

These pin existing behavior of copied code. If an assertion fails, read the function and correct the assertion to the bound the code documents; do not change the code in this task.

```python
from pathlib import Path

import digest


def test_output_is_bounded():
    out = digest.digest("line\n" * 500, grep=r"^never$", tail=12, max_bytes=1024)
    assert len(out.splitlines()) <= digest.MAX_LINES + 1
    assert len(out.encode("utf-8")) <= 1024


def test_main_reads_file(tmp_path: Path, capsys):
    target = tmp_path / "a.txt"
    target.write_text("one\ntwo\n", encoding="utf-8")
    assert digest.main([str(target)]) == 0
    assert capsys.readouterr().out.startswith("lines 2")
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest plugins/crepidoma-core/tests/test_digest.py`
Expected: `2 passed`

- [ ] **Step 5: Write launchers**

`plugins/crepidoma-core/bin/digest`:

```sh
#!/bin/sh
exec uv run --no-project --quiet python "$(dirname "$0")/../scripts/digest.py" "$@"
```

`plugins/crepidoma-core/bin/digest.cmd`:

```bat
@uv run --no-project --quiet python "%~dp0..\scripts\digest.py" %*
```

Run: `git add plugins/crepidoma-core/bin/digest && git update-index --chmod=+x plugins/crepidoma-core/bin/digest`
Expected: exit 0.

Run: `printf 'a\nb\n' | sh plugins/crepidoma-core/bin/digest`
Expected: first line `lines 2 bytes 4`.

- [ ] **Step 6: Validate and commit**

Run: `claude plugin validate .`
Expected: validation passes for marketplace and plugin.

```bash
git add .claude-plugin plugins/crepidoma-core
git commit -m "feat(plugin): add crepidoma marketplace, core plugin and digest"
```

---

### Task 6: raw_read_guard and PreToolUse hook

**Files:**

- Create: `plugins/crepidoma-core/scripts/raw_read_guard.py` (copied, two edits), `plugins/crepidoma-core/hooks/hooks.json`
- Test: `plugins/crepidoma-core/tests/test_raw_read_guard.py`, `plugins/crepidoma-core/tests/test_hooks_json.py`

**Interfaces:**

- Consumes: `bin/digest` from Task 5.
- Produces: module `raw_read_guard` with `MAX_LINES = 20`, `decide(data: dict) -> str | None`, `main() -> int`; `hooks/hooks.json` with a `PreToolUse` entry.

- [ ] **Step 1: Copy guard**

Run: `cp ~/.claude/bin/raw_read_guard.py plugins/crepidoma-core/scripts/raw_read_guard.py`

- [ ] **Step 2: Write tests (characterization plus the two new behaviors)**

```python
import io
import json

import raw_read_guard as guard


def read(limit=None, path="notes.py", agent=None):
    data = {"tool_name": "Read", "tool_input": {"file_path": path}}
    if limit is not None:
        data["tool_input"]["limit"] = limit
    if agent:
        data["agent_id"] = agent
    return data


def bash(command):
    return {"tool_name": "Bash", "tool_input": {"command": command}}


def test_subagent_always_allowed():
    assert guard.decide(read(agent="a1")) is None


def test_read_needs_small_limit():
    assert guard.decide(read()) is not None
    assert guard.decide(read(limit=200)) is not None
    assert guard.decide(read(limit=20)) is None


def test_images_allowed():
    assert guard.decide(read(path="shot.PNG")) is None


def test_bash_raw_reads_denied():
    assert guard.decide(bash("cat README.md")) is not None
    assert guard.decide(bash("head -n 40 README.md")) is not None


def test_bash_plain_commands_allowed():
    assert guard.decide(bash("git status")) is None


def test_plugin_digest_is_a_sink():
    assert guard.decide(bash("cat README.md | digest")) is None
    assert guard.decide(bash("cat README.md | digest --tail 5")) is None


def test_reason_points_at_plugin_digest():
    assert "digest" in guard.decide(read())
    assert "~/.claude/bin" not in guard.decide(read())


def test_malformed_stdin_fails_open(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("not json"))
    assert guard.main() == 0
    assert capsys.readouterr().out == ""


def test_denial_contract(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(read())))
    assert guard.main() == 0
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
```

- [ ] **Step 3: Run tests to verify the new behaviors fail**

Run: `uv run pytest plugins/crepidoma-core/tests/test_raw_read_guard.py`
Expected: FAIL on `test_plugin_digest_is_a_sink` and `test_reason_points_at_plugin_digest`; all others pass. If a characterization test fails, correct the assertion to the code's actual behavior.

- [ ] **Step 4: Apply the two edits in `raw_read_guard.py`**

Replace the digest sink pattern:

```python
(re.compile(r"(^|[\s/\\])digest(\.py)?\b"),)
```

Replace the digest hint constant:

```python
DIGEST = "digest"
```

Replace any docstring mention of `Tasks/claude/hooks.py` with `scripts/hooks.py`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest plugins/crepidoma-core/tests/test_raw_read_guard.py`
Expected: `9 passed`

- [ ] **Step 6: Write `hooks/hooks.json` and its test**

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Read|Bash",
        "hooks": [
          {
            "type": "command",
            "command": "uv run --no-project --quiet python \"${CLAUDE_PLUGIN_ROOT}/scripts/raw_read_guard.py\""
          }
        ]
      }
    ]
  }
}
```

`plugins/crepidoma-core/tests/test_hooks_json.py`:

```python
import json
import re
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
QUOTED_SCRIPT = re.compile(r'"\$\{CLAUDE_PLUGIN_ROOT\}/([^"]+)"')


def load():
    return json.loads((PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8"))


def commands():
    for groups in load()["hooks"].values():
        for group in groups:
            for hook in group["hooks"]:
                yield hook["command"]


def test_commands_quote_plugin_root_and_scripts_exist():
    found = list(commands())
    assert found
    for command in found:
        match = QUOTED_SCRIPT.search(command)
        assert match, command
        assert (PLUGIN / match.group(1)).is_file(), command


def test_expected_events():
    assert {"PreToolUse"} <= set(load()["hooks"])
```

Run: `uv run pytest plugins/crepidoma-core/tests`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add plugins/crepidoma-core
git commit -m "feat(plugin): ship raw-read guard as PreToolUse hook"
```

---

### Task 7: Directive injector and SessionStart hook

**Files:**

- Create: `plugins/crepidoma-core/scripts/inject_directives.py`, `plugins/crepidoma-core/directives/.gitkeep`
- Modify: `plugins/crepidoma-core/hooks/hooks.json`, `plugins/crepidoma-core/tests/test_hooks_json.py`
- Test: `plugins/crepidoma-core/tests/test_inject_directives.py`

**Interfaces:**

- Produces: `DIRECTIVES: Path`, `LIMIT = 10_000`, `TRUNCATED: str`, `build(directory: Path) -> str` (raises `FileNotFoundError` when the directory is missing), `payload(text: str) -> dict`, `main() -> int`.

- [ ] **Step 1: Write the failing tests**

```python
import json
from pathlib import Path

import inject_directives as inj


def context(capsys) -> str:
    return json.loads(capsys.readouterr().out)["hookSpecificOutput"]["additionalContext"]


def test_build_orders_and_joins(tmp_path: Path):
    (tmp_path / "20-b.md").write_text("B\n", encoding="utf-8")
    (tmp_path / "10-a.md").write_text("A\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("ignored", encoding="utf-8")
    assert inj.build(tmp_path) == "A\n\nB"


def test_main_emits_session_start_json(tmp_path: Path, monkeypatch, capsys):
    (tmp_path / "10-a.md").write_text("rule one\n", encoding="utf-8")
    monkeypatch.setattr(inj, "DIRECTIVES", tmp_path)
    assert inj.main() == 0
    data = json.loads(capsys.readouterr().out)
    assert data == {
        "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "rule one"}
    }


def test_missing_directory_fails_open(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr(inj, "DIRECTIVES", tmp_path / "absent")
    assert inj.main() == 0
    assert context(capsys).startswith("Crepidoma directives unavailable")


def test_oversize_is_truncated_with_notice(tmp_path: Path, monkeypatch, capsys):
    (tmp_path / "10-a.md").write_text("x" * (inj.LIMIT + 50), encoding="utf-8")
    monkeypatch.setattr(inj, "DIRECTIVES", tmp_path)
    assert inj.main() == 0
    text = context(capsys)
    assert len(text) <= inj.LIMIT
    assert text.endswith(inj.TRUNCATED)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest plugins/crepidoma-core/tests/test_inject_directives.py`
Expected: FAIL, `ModuleNotFoundError: No module named 'inject_directives'`

- [ ] **Step 3: Implement `scripts/inject_directives.py`**

```python
"""SessionStart hook: emit Crepidoma directives as additional context.

Reads directives/*.md in name order and prints the SessionStart JSON contract.
Never blocks a session: failures become a one-line notice in the context.
"""

from __future__ import annotations

import json
from pathlib import Path

DIRECTIVES = Path(__file__).resolve().parent.parent / "directives"
LIMIT = 10_000
TRUNCATED = "\n[crepidoma: directives truncated at 10000 characters]"


def build(directory: Path) -> str:
    if not directory.is_dir():
        raise FileNotFoundError(directory)
    parts = [path.read_text(encoding="utf-8").strip() for path in sorted(directory.glob("*.md"))]
    return "\n\n".join(parts)


def payload(text: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}


def main() -> int:
    try:
        text = build(DIRECTIVES)
    except OSError as error:
        text = f"Crepidoma directives unavailable: {error}"
    if len(text) > LIMIT:
        text = text[: LIMIT - len(TRUNCATED)] + TRUNCATED
    print(json.dumps(payload(text)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest plugins/crepidoma-core/tests/test_inject_directives.py`
Expected: `4 passed`

- [ ] **Step 5: Replace `hooks/hooks.json`**

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "uv run --no-project --quiet python \"${CLAUDE_PLUGIN_ROOT}/scripts/inject_directives.py\""
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Read|Bash",
        "hooks": [
          {
            "type": "command",
            "command": "uv run --no-project --quiet python \"${CLAUDE_PLUGIN_ROOT}/scripts/raw_read_guard.py\""
          }
        ]
      }
    ]
  }
}
```

In `test_hooks_json.py` change the last assertion to:

```python
    assert {"SessionStart", "PreToolUse"} <= set(load()["hooks"])
```

- [ ] **Step 6: Run plugin tests, validate, commit**

Run: `uv run pytest plugins/crepidoma-core/tests && claude plugin validate .`
Expected: all pass; validation passes.

```bash
git add plugins/crepidoma-core
git commit -m "feat(plugin): inject directives at SessionStart"
```

---

### Task 8: Merge directives

**Files:**

- Create: `plugins/crepidoma-core/directives/10-communication-style.md`, `20-tool-first-loop.md`, `30-conventions.md`, `40-models.md`, `50-skills-and-plugins.md`, `60-taskfile-shell.md`
- Delete: `plugins/crepidoma-core/directives/.gitkeep`
- Test: `plugins/crepidoma-core/tests/test_shipped_directives.py`

**Interfaces:**

- Consumes: `inject_directives.build`, `inject_directives.DIRECTIVES`, `inject_directives.LIMIT`.

- [ ] **Step 1: Write the failing test**

```python
import inject_directives as inj

EXPECTED = {
    "10-communication-style.md",
    "20-tool-first-loop.md",
    "30-conventions.md",
    "40-models.md",
    "50-skills-and-plugins.md",
    "60-taskfile-shell.md",
}


def test_shipped_directives_present_and_fit():
    names = {path.name for path in inj.DIRECTIVES.glob("*.md")}
    assert names == EXPECTED
    text = inj.build(inj.DIRECTIVES)
    assert 0 < len(text) <= inj.LIMIT


def test_no_user_scope_paths():
    text = inj.build(inj.DIRECTIVES)
    assert "~/.claude/bin" not in text
```

Run: `uv run pytest plugins/crepidoma-core/tests/test_shipped_directives.py`
Expected: FAIL, names mismatch.

- [ ] **Step 2: Dispatch `merge-curator`**

Brief (verbatim):

```text
Family: directives.
Sources (relative to PILLARS, plus the user-scope file):
  ~/.claude/CLAUDE.md (sections: CARDINAL DIRECTIVE, Tool-first loop, Communication style)
  */CLAUDE.md (sections: conventions, tool-first loop, models, skills and plugins, graphify)
  */.claude/rules/taskfile-shell.md
Targets in plugins/crepidoma-core/directives/:
  10-communication-style.md  cardinal no-first-person rule + communication style
  20-tool-first-loop.md      tool-first loop, subagent rules, output caps
  30-conventions.md          shared conventions
  40-models.md               model selection rules
  50-skills-and-plugins.md   skills/plugins usage, graphify trigger as third-party reference
  60-taskfile-shell.md       Taskfile shell rules
Family rules: numbered lists only, imperative, no first person; replace
`python ~/.claude/bin/digest.py` with `digest`; total of all six files <= 9,000 characters
(headroom under the 10,000 cap); one H1 per file.
```

Expected receipt: six targets written, counts of conflicts and exclusions, pytest and scrub results.

- [ ] **Step 3: Verify**

Run: `git rm -q plugins/crepidoma-core/directives/.gitkeep; uv run pytest plugins/crepidoma-core/tests`
Expected: all pass.

Run: `uv run python plugins/crepidoma-core/scripts/inject_directives.py | uv run python plugins/crepidoma-core/scripts/digest.py`
Expected: a single JSON line, `bytes` under 10,500.

- [ ] **Step 4: Maintainer review checkpoint**

Report the conflict count from `.local/merge-conflicts.md` to the user before committing. Commit after the user accepts or edits.

- [ ] **Step 5: Commit**

```bash
git add plugins/crepidoma-core/directives plugins/crepidoma-core/tests/test_shipped_directives.py
git commit -m "feat(plugin): merge shared directives from pillar repos"
```

---

### Task 9: Merge agents

**Files:**

- Create: `plugins/crepidoma-core/agents/*.md`
- Test: `plugins/crepidoma-core/tests/test_agents.py`

- [ ] **Step 1: Write the failing test**

```python
import re
from pathlib import Path

AGENTS = Path(__file__).resolve().parent.parent / "agents"
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def frontmatter(path: Path) -> dict[str, str]:
    match = FRONTMATTER.match(path.read_text(encoding="utf-8"))
    assert match, path.name
    fields = {}
    for line in match.group(1).splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def test_agents_have_required_fields_and_unique_names():
    files = sorted(AGENTS.glob("*.md"))
    assert len(files) >= 3
    names = []
    for path in files:
        fields = frontmatter(path)
        assert fields.get("name") == path.stem
        assert fields.get("description")
        assert fields.get("tools"), "agents carry only the tools they use"
        names.append(fields["name"])
    assert len(names) == len(set(names))
```

Run: `uv run pytest plugins/crepidoma-core/tests/test_agents.py`
Expected: FAIL, `assert 0 >= 3`.

- [ ] **Step 2: Dispatch `merge-curator`**

```text
Family: agents.
Sources: */.claude/agents/*.md (relative to PILLARS).
Targets: plugins/crepidoma-core/agents/<role>.md, one file per role.
Family rules: cluster same-role agents across repos (for example tool-smith and toolsmith,
auditor and tooling-auditor); file stem = frontmatter name, kebab-case; union of rules and
checks; tools list = union actually used by the merged body, nothing more; keep the most
specific model setting and log alternatives; repo-specific agents with no counterpart are
excluded and logged to .local/repo-local.md unless their rules are generic.
```

- [ ] **Step 3: Verify and commit**

Run: `uv run pytest plugins/crepidoma-core/tests && claude plugin validate .`
Expected: all pass.

```bash
git add plugins/crepidoma-core/agents plugins/crepidoma-core/tests/test_agents.py
git commit -m "feat(plugin): merge shared agents from pillar repos"
```

---

### Task 10: Merge hooks.py and shared Taskfiles

**Files:**

- Create: `plugins/crepidoma-core/scripts/hooks.py`, `taskfiles/claude/Taskfile.yml`, `taskfiles/lint/Taskfile.yml`, supporting scripts referenced by those Taskfiles under `taskfiles/<ns>/`
- Test: `plugins/crepidoma-core/tests/test_hooks_py.py`, `tests/test_taskfiles.py`

- [ ] **Step 1: Write the Taskfile structure test**

```python
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_shared_taskfiles_list_tasks():
    for namespace in ("claude", "lint"):
        taskfile = ROOT / "taskfiles" / namespace / "Taskfile.yml"
        assert taskfile.is_file(), namespace
        result = subprocess.run(
            ["task", "--taskfile", str(taskfile), "--list-all"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        assert "task:" not in result.stderr.lower()


def test_taskfiles_use_taskfile_dir_for_paths():
    for taskfile in (ROOT / "taskfiles").rglob("Taskfile.yml"):
        text = taskfile.read_text(encoding="utf-8")
        assert "../" not in text or "{{.TASKFILE_DIR}}" in text, taskfile
```

Run: `uv run pytest tests/test_taskfiles.py`
Expected: FAIL, `taskfiles/claude/Taskfile.yml` missing.

- [ ] **Step 2: Dispatch `merge-curator`**

```text
Family: taskfiles-and-hooks.
Sources: */tasks/claude/**, */Tasks/claude/**, */tasks/lint/**, */Tasks/lint/**,
*/tasks/precommit/**, */tasks/git/**, */Tasks/qa/**, and any tests of hooks.py found
under */tests/** (relative to PILLARS).
Targets: plugins/crepidoma-core/scripts/hooks.py (superset of all hooks.py copies);
taskfiles/claude/Taskfile.yml and taskfiles/lint/Taskfile.yml with helper scripts beside them;
plugins/crepidoma-core/tests/test_hooks_py.py.
Family rules: hooks.py keeps one CLI with one subcommand per hook, stdin JSON contract,
fail-open on malformed input; tests: port every existing pillar test, then add for each
subcommand one allow case, one deny case and one malformed-stdin case; Taskfile paths
resolve from {{.TASKFILE_DIR}} so the files work when included from .crepidoma/;
pillar-specific task bodies (product build, deploy) are excluded and logged.
```

- [ ] **Step 3: Verify and commit**

Run: `uv run pytest`
Expected: all pass.

```bash
git add plugins/crepidoma-core/scripts/hooks.py plugins/crepidoma-core/tests/test_hooks_py.py taskfiles tests/test_taskfiles.py
git commit -m "feat: merge shared hooks.py and claude/lint Taskfiles"
```

---

### Task 11: Merge shared configs

**Files:**

- Create: `configs/.editorconfig`, `configs/.gitattributes`, `configs/.prettierrc`, `configs/eslint.config.js`, `configs/ruff.toml`, `configs/.yamllint`, `configs/sgconfig.yml`, `configs/ast-grep/rules/*.yml`, `configs/gitleaks.toml`, `configs/semgrep/rules.yml`, `configs/zizmor.yml`, `configs/.hadolint.yaml`, `configs/tsconfig.base.json`
- Modify: root `.editorconfig`, `.gitattributes`, `.prettierrc`, `.yamllint`, `pyproject.toml` (ruff section), `.pre-commit-config.yaml` (ast-grep hook, gitleaks config)
- Test: `tests/test_configs.py`

- [ ] **Step 1: Write the failing test**

```python
import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIGS = ROOT / "configs"
EXPECTED = [
    ".editorconfig",
    ".gitattributes",
    ".prettierrc",
    "eslint.config.js",
    "ruff.toml",
    ".yamllint",
    "sgconfig.yml",
    "gitleaks.toml",
    "semgrep/rules.yml",
    "zizmor.yml",
    ".hadolint.yaml",
    "tsconfig.base.json",
]


def test_all_configs_present():
    missing = [name for name in EXPECTED if not (CONFIGS / name).is_file()]
    assert missing == []


def test_structured_configs_parse():
    tomllib.loads((CONFIGS / "ruff.toml").read_text(encoding="utf-8"))
    tomllib.loads((CONFIGS / "gitleaks.toml").read_text(encoding="utf-8"))
    json.loads((CONFIGS / ".prettierrc").read_text(encoding="utf-8"))


def test_root_ruff_extends_shared():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["tool"]["ruff"]["extend"] == "configs/ruff.toml"
```

Run: `uv run pytest tests/test_configs.py`
Expected: FAIL.

- [ ] **Step 2: Dispatch `merge-curator`**

```text
Family: configs.
Sources (relative to PILLARS): */.editorconfig, */.gitattributes, */.prettierrc*,
*/prettier.config.*, */eslint.config.*, */.eslintrc*, */ruff.toml, */pyproject.toml [tool.ruff]
and [tool.black], */.yamllint*, */sgconfig.yml, */tasks/sg/rules/**, */.gitleaks.toml,
*/.semgrep*, */zizmor.yml, */.hadolint.yaml, */tsconfig*.json, */.pre-commit-config.yaml,
*/.cicd/**.
Targets: the configs/ files listed in Task 11 of the plan.
Family rules: black settings fold into ruff.toml [format]; biome rules map to eslint/prettier
equivalents where they exist, others logged; eslint.config.js is flat config, ESM, depends
only on @eslint/js and typescript-eslint; tsconfig.base.json holds compilerOptions only;
ast-grep rules must be language-generic or tagged by language; gitleaks.toml extends the
default ruleset ([extend] useDefault = true) and allowlists the scrub test fixtures path.
```

- [ ] **Step 3: Point Crepidoma at the shared configs**

1. Replace root `[tool.ruff]` and `[tool.ruff.lint]` in `pyproject.toml` with:

```toml
[tool.ruff]
extend = "configs/ruff.toml"
```

2. Replace root `.editorconfig`, `.gitattributes`, `.prettierrc`, `.yamllint` with copies of the `configs/` versions (pre-commit tools read root files; `tools/drift_map.toml` in Task 12 maps these copies).
3. The gitleaks hook reads root `.gitleaks.toml` by default; add that file containing:

```toml
[extend]
path = "configs/gitleaks.toml"
```

4. Add to `.pre-commit-config.yaml` before the `local` repo:

```yaml
- repo: https://github.com/ast-grep/ast-grep
  rev: 0.28.0
  hooks:
    - id: ast-grep
      args: [scan, --config, configs/sgconfig.yml]
      pass_filenames: false
```

Then run `uv run pre-commit autoupdate --repo https://github.com/ast-grep/ast-grep`.

- [ ] **Step 4: Verify and commit**

Run: `uv run pytest && task fmt && task hooks:pre-commit`
Expected: all pass.

```bash
git add -A
git commit -m "feat(configs): merge shared lint, format and security configs"
```

---

### Task 12: drift_check

**Files:**

- Create: `tools/drift_check.py`, `tools/drift_map.toml`
- Test: `tests/test_drift_check.py`
- Modify: `Taskfile.yml` (add `drift`)

**Interfaces:**

- Produces: `ROOT: Path`, `DEFAULT_MAP: Path`, `MAX_SHOWN = 15`, `load_map(path: Path) -> list[dict]`, `check(pillar: Path, entries: list[dict], root: Path) -> list[tuple[str, str, str]]` with states `duplicate | drifted | absent`, `main(argv) -> int` (exit 0 clean, 1 on duplicate or drifted, 2 when pillar is not a directory).

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path

import drift_check


def make(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def test_states_with_crlf_normalised(tmp_path: Path):
    root, pillar = tmp_path / "crep", tmp_path / "pillar"
    make(root / "a/same.py", b"one\n")
    make(pillar / "x/same.py", b"one\r\n")
    make(root / "a/diff.py", b"one\n")
    make(pillar / "x/diff.py", b"two\n")
    make(root / "a/gone.py", b"one\n")
    entries = [
        {"crepidoma": "a/same.py", "pillar": ["y/same.py", "x/same.py"]},
        {"crepidoma": "a/diff.py", "pillar": ["x/diff.py"]},
        {"crepidoma": "a/gone.py", "pillar": ["x/gone.py"]},
    ]
    assert drift_check.check(pillar, entries, root) == [
        ("duplicate", "a/same.py", "x/same.py"),
        ("drifted", "a/diff.py", "x/diff.py"),
        ("absent", "a/gone.py", "-"),
    ]


def test_main_rejects_missing_pillar(tmp_path: Path):
    assert drift_check.main([str(tmp_path / "nope")]) == 2


def test_main_exit_and_report(tmp_path: Path, capsys):
    root, pillar = tmp_path / "crep", tmp_path / "pillar"
    make(root / "a/f.py", b"one\n")
    make(pillar / "a/f.py", b"two\n")
    mapping = tmp_path / "map.toml"
    mapping.write_text('[[file]]\ncrepidoma = "a/f.py"\npillar = ["a/f.py"]\n', encoding="utf-8")
    report = tmp_path / "report.tsv"
    args = [str(pillar), "--map", str(mapping), "--root", str(root), "--report", str(report)]
    assert drift_check.main(args) == 1
    assert "drifted" in report.read_text(encoding="utf-8")
    assert "drifted=1" in capsys.readouterr().out


def test_repo_map_sources_exist():
    entries = drift_check.load_map(drift_check.DEFAULT_MAP)
    assert entries
    for entry in entries:
        assert (drift_check.ROOT / entry["crepidoma"]).is_file(), entry["crepidoma"]
```

Run: `uv run pytest tests/test_drift_check.py`
Expected: FAIL, `ModuleNotFoundError: No module named 'drift_check'`

- [ ] **Step 2: Implement `tools/drift_check.py`**

```python
"""Compare a pillar checkout with Crepidoma-owned files.

Usage: drift_check.py PILLAR [--map FILE] [--root DIR] [--report FILE]
States: duplicate (identical copy, delete it), drifted (local divergence), absent (linked, good).
Exit 0 when every entry is absent, 1 on duplicate or drifted, 2 when PILLAR is not a directory.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import tomllib
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MAP = ROOT / "tools" / "drift_map.toml"
MAX_SHOWN = 15
STATES = ("duplicate", "drifted", "absent")


def load_map(path: Path) -> list[dict]:
    return tomllib.loads(path.read_text(encoding="utf-8"))["file"]


def fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def check(pillar: Path, entries: list[dict], root: Path) -> list[tuple[str, str, str]]:
    rows = []
    for entry in entries:
        source = root / entry["crepidoma"]
        copy = next((pillar / c for c in entry["pillar"] if (pillar / c).is_file()), None)
        if copy is None:
            rows.append(("absent", entry["crepidoma"], "-"))
            continue
        state = "duplicate" if fingerprint(copy) == fingerprint(source) else "drifted"
        rows.append((state, entry["crepidoma"], copy.relative_to(pillar).as_posix()))
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pillar", type=Path)
    parser.add_argument("--map", type=Path, default=DEFAULT_MAP)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    if not args.pillar.is_dir():
        print(f"not a directory: {args.pillar}", file=sys.stderr)
        return 2
    rows = check(args.pillar, load_map(args.map), args.root)
    lines = [f"{state}\t{source}\t{copy}" for state, source, copy in rows]
    if args.report:
        args.report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    flagged = [line for line in lines if not line.startswith("absent")]
    for line in flagged[:MAX_SHOWN]:
        print(line)
    if len(flagged) > MAX_SHOWN:
        print(f"... {len(flagged) - MAX_SHOWN} more")
    counts = Counter(row[0] for row in rows)
    print(" ".join(f"{state}={counts[state]}" for state in STATES))
    return 1 if flagged else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Write `tools/drift_map.toml`**

Start with these entries, then append one `[[file]]` per agent, Taskfile helper and config target, using the alias lists in `.local/merge-log/*.md` for the `pillar` arrays (old file names only, never repo names).

```toml
[[file]]
crepidoma = "plugins/crepidoma-core/scripts/raw_read_guard.py"
pillar = ["Tasks/claude/raw_read_guard.py", "tasks/claude/raw_read_guard.py"]

[[file]]
crepidoma = "plugins/crepidoma-core/scripts/hooks.py"
pillar = ["Tasks/claude/hooks.py", "tasks/claude/hooks.py"]

[[file]]
crepidoma = "plugins/crepidoma-core/directives/60-taskfile-shell.md"
pillar = [".claude/rules/taskfile-shell.md"]

[[file]]
crepidoma = "taskfiles/claude/Taskfile.yml"
pillar = ["Tasks/claude/Taskfile.yml", "tasks/claude/Taskfile.yml"]

[[file]]
crepidoma = "taskfiles/lint/Taskfile.yml"
pillar = ["Tasks/lint/Taskfile.yml", "tasks/lint/Taskfile.yml"]

[[file]]
crepidoma = "configs/.editorconfig"
pillar = [".editorconfig"]

[[file]]
crepidoma = "configs/.gitattributes"
pillar = [".gitattributes"]

[[file]]
crepidoma = "configs/.prettierrc"
pillar = [".prettierrc"]

[[file]]
crepidoma = "configs/.yamllint"
pillar = [".yamllint", ".yamllint.yml", ".yamllint.yaml"]

[[file]]
crepidoma = "configs/ruff.toml"
pillar = ["ruff.toml"]
```

- [ ] **Step 4: Run tests, add task, try on one pillar**

Run: `uv run pytest tests/test_drift_check.py`
Expected: `4 passed`

Add to `Taskfile.yml`:

```yaml
drift:
  desc: "Compare a pillar with Crepidoma: task drift -- <pillar path>"
  cmds:
    - uv run python tools/drift_check.py {{.CLI_ARGS}} --report .local/drift-report.tsv
```

Run: `mkdir -p .local && task drift -- ../<any pillar dir>`
Expected: bounded listing, final line `duplicate=<n> drifted=<n> absent=<n>`, exit 1 (pillars still hold copies).

- [ ] **Step 5: Commit**

```bash
git add tools/drift_check.py tools/drift_map.toml tests/test_drift_check.py Taskfile.yml
git commit -m "feat(tools): add pillar drift check"
```

---

### Task 13: Pillar-facing pre-commit hooks

**Files:**

- Create: `.pre-commit-hooks.yaml`
- Test: `tests/test_precommit_hooks.py`

**Interfaces:**

- Consumes: console scripts `crepidoma-scrub`, `crepidoma-ratchet`, `crepidoma-drift` from `pyproject.toml`.
- Produces: hook ids `crepidoma-scrub`, `crepidoma-long-files`.

- [ ] **Step 1: Write the failing test**

```python
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_try_repo_scrub_passes_on_readme():
    result = subprocess.run(
        [
            "uv",
            "run",
            "pre-commit",
            "try-repo",
            str(ROOT),
            "crepidoma-scrub",
            "--files",
            "README.md",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout[-800:]
    assert "Passed" in result.stdout
```

Run: `uv run pytest tests/test_precommit_hooks.py`
Expected: FAIL, `.pre-commit-hooks.yaml is not a file`.

- [ ] **Step 2: Write `.pre-commit-hooks.yaml`**

```yaml
- id: crepidoma-scrub
  name: crepidoma scrub (paths, emails, tokens, private names)
  description: Rejects local paths, emails, tokens and names listed in .scrub-denylist
  entry: crepidoma-scrub
  language: python
  types: [text]
- id: crepidoma-long-files
  name: crepidoma long-file ratchet
  description: Files over 400 lines must be baselined in .ratchet/long-files.baseline and may not grow
  entry: crepidoma-ratchet long-files --max-lines 400
  language: python
  types: [text]
```

- [ ] **Step 3: Verify and commit**

Run: `uv run pytest tests/test_precommit_hooks.py`
Expected: `1 passed` (try-repo builds the package from the working tree, so the test also proves the hatch packaging).

```bash
git add .pre-commit-hooks.yaml tests/test_precommit_hooks.py
git commit -m "feat: publish crepidoma pre-commit hooks for pillars"
```

---

### Task 14: Process ADRs

**Files:**

- Create: `docs/adr/README.md`, `docs/adr/template.md`, `docs/adr/0001-*.md` through `docs/adr/0006-*.md`, `docs/adr/0007-crepidoma-as-foundation.md`
- Test: `tests/test_adrs.py`

- [ ] **Step 1: Write the failing test**

```python
import re
from pathlib import Path

ADR = Path(__file__).resolve().parent.parent / "docs" / "adr"
NAME = re.compile(r"^\d{4}-[a-z0-9-]+\.md$")
REQUIRED = ("## Status", "## Context", "## Decision", "## Consequences")


def test_adrs_numbered_and_structured():
    adrs = sorted(p for p in ADR.glob("*.md") if NAME.match(p.name))
    assert len(adrs) >= 7
    numbers = [int(p.name[:4]) for p in adrs]
    assert numbers == list(range(1, len(adrs) + 1))
    for path in adrs:
        text = path.read_text(encoding="utf-8")
        for heading in REQUIRED:
            assert heading in text, f"{path.name}: {heading}"


def test_index_lists_every_adr():
    index = (ADR / "README.md").read_text(encoding="utf-8")
    for path in ADR.glob("*.md"):
        if NAME.match(path.name):
            assert path.name in index
```

Run: `uv run pytest tests/test_adrs.py`
Expected: FAIL.

- [ ] **Step 2: Dispatch `merge-curator`**

```text
Family: adrs.
Sources: */docs/**/adr*/**/*.md and */docs/**/decisions/**/*.md (relative to PILLARS).
Targets: docs/adr/template.md (merged template with Status, Context, Decision, Consequences);
docs/adr/0001..0006 for the process topics: tool-first loop, two-tier local gates,
uv tooling, taskfile as the interface, ratcheting baselines, testing strategy;
docs/adr/README.md index (number, title, status, one line).
Family rules: only process ADRs, never product ADRs; one ADR per topic merging all variants;
Status "Accepted" with date 2026-10-20 and a line "Supersedes the per-pillar ADRs on this topic";
log source ADR paths per topic to .local/merge-log/adrs.md (pillars use it to write
"superseded by" stubs during migration).
```

- [ ] **Step 3: Write `docs/adr/0007-crepidoma-as-foundation.md`**

```markdown
# 0007. Crepidoma as the foundation for pillar projects

## Status

Accepted, 2026-10-20.

## Context

Pillar repos carried drifted copies of agents, hook scripts, Taskfiles, lint and security
configs, CLAUDE.md sections and process ADRs. No copy was identical to another. CLAUDE.md
cannot import URLs; Claude Code plugins cannot ship CLAUDE.md, permissions or statusLine.

## Decision

1. Claude assets ship as the `crepidoma-core` plugin from the `crepidoma` marketplace in this repo.
   Directives reach sessions through a SessionStart hook, capped at 10,000 characters.
2. Taskfiles and configs ship through a `.crepidoma` git submodule.
3. Commit gates ship as pre-commit hooks from this repo (`.pre-commit-hooks.yaml`).
4. Third-party plugins and skills are referenced in templates, never copied.
5. `tools/drift_check.py` reports pillar copies that should be deleted or reconciled.

## Consequences

1. A pillar adopts Crepidoma with three committed references and one install command per collaborator.
2. Changes land once, here, and reach pillars on plugin update, submodule bump or pre-commit autoupdate.
3. Every push here is public: scrub_check and gitleaks gate every commit and push.
4. Repo-specific rules stay in each pillar's CLAUDE.md.
```

Add its row to `docs/adr/README.md`.

- [ ] **Step 4: Verify and commit**

Run: `uv run pytest tests/test_adrs.py && task sec`
Expected: pass.

```bash
git add docs/adr tests/test_adrs.py
git commit -m "docs(adr): merge process ADRs and record foundation decision"
```

---

### Task 15: Templates and migration guide

**Files:**

- Create: `templates/settings.json`, `templates/CLAUDE.md`, `templates/.pre-commit-config.yaml`, `templates/gitmodules.txt`, `templates/Taskfile.includes.yml`, `docs/migration.md`
- Test: `tests/test_templates.py`

- [ ] **Step 1: Write the failing test**

No third-party YAML parser; YAML structure is checked by text.

```python
import json
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"


def test_settings_template_links_marketplace():
    data = json.loads((TEMPLATES / "settings.json").read_text(encoding="utf-8"))
    source = data["extraKnownMarketplaces"]["crepidoma"]["source"]
    assert source == {"source": "github", "repo": "Levia-Labs/Crepidoma"}
    assert data["enabledPlugins"]["crepidoma-core@crepidoma"] is True


def test_precommit_template_links_repo():
    text = (TEMPLATES / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    assert "repo: https://github.com/Levia-Labs/Crepidoma" in text
    assert "id: crepidoma-scrub" in text


def test_taskfile_includes_point_into_submodule():
    text = (TEMPLATES / "Taskfile.includes.yml").read_text(encoding="utf-8")
    assert ".crepidoma/taskfiles/claude" in text
    assert ".crepidoma/taskfiles/lint" in text
```

Run: `uv run pytest tests/test_templates.py`
Expected: FAIL, files missing.

- [ ] **Step 2: Write `templates/Taskfile.includes.yml` and `templates/gitmodules.txt`**

```yaml
# Merge into the pillar's root Taskfile.yml
includes:
  claude: .crepidoma/taskfiles/claude
  lint: .crepidoma/taskfiles/lint
```

```text
git submodule add https://github.com/Levia-Labs/Crepidoma .crepidoma
git submodule update --init
```

- [ ] **Step 3: Dispatch `merge-curator` for settings and pre-commit templates**

```text
Family: templates.
Sources: */.claude/settings.json (relative to PILLARS); ~/.claude/settings.json (enabledPlugins,
extraKnownMarketplaces only); ~/.claude/plugins/installed_plugins.json and
~/.claude/plugins/known_marketplaces.json (names and sources only); */.pre-commit-config.yaml.
Targets: templates/settings.json, templates/.pre-commit-config.yaml, templates/CLAUDE.md.
Family rules: settings.json = extraKnownMarketplaces (crepidoma github Levia-Labs/Crepidoma plus
every third-party marketplace in use) + enabledPlugins (crepidoma-core@crepidoma plus shared
third-party plugins) + the permissions allow/deny entries common to 2+ pillars; no hooks block
(the plugin ships hooks); no absolute paths, no env values, no autoMode block.
.pre-commit-config.yaml = Crepidoma repo hooks (crepidoma-scrub, crepidoma-long-files) +
ruff, ruff-format, prettier, eslint (local hook, npx), gitleaks, yamllint, shellcheck, actionlint,
zizmor, hadolint (hadolint-py), ast-grep, all pointing config args at .crepidoma/configs/;
pre-push stage: semgrep and osv-scanner marked optional with a comment.
CLAUDE.md = skeleton with headings: Project, Stack, Repo-specific rules, Commands; first line
states that shared directives come from the crepidoma-core plugin.
```

- [ ] **Step 4: Write `docs/migration.md`**

```markdown
# Migrating a pillar to Crepidoma

1. Add the submodule: run the two commands in `templates/gitmodules.txt`.
2. Merge `templates/Taskfile.includes.yml` into the pillar `Taskfile.yml`; delete the pillar's
   own `tasks/claude`, `tasks/lint` (or `Tasks/...`) directories.
3. Merge `templates/settings.json` into `.claude/settings.json`; delete the pillar hooks block
   that ran `hooks.py` or `raw_read_guard.py`.
4. Each collaborator runs once: `claude plugin install crepidoma-core@crepidoma --scope project`.
5. Replace `.pre-commit-config.yaml` with `templates/.pre-commit-config.yaml`, keep pillar-only
   hooks, run `pre-commit install && pre-commit autoupdate`.
6. Point root configs at `.crepidoma/configs/` (ruff `extend`, prettier/yamllint copies,
   `.gitleaks.toml` `[extend] path`).
7. Shrink `CLAUDE.md` to `templates/CLAUDE.md` plus repo-specific rules.
8. Replace process ADRs with stubs: "Superseded by Crepidoma ADR-000N" linking
   `https://github.com/Levia-Labs/Crepidoma/blob/main/docs/adr/`.
9. Run `task drift -- <pillar path>` from the Crepidoma checkout until it reports
   `duplicate=0 drifted=0`.
10. Open one PR per pillar.

## User scope

1. Back up `~/.claude/CLAUDE.md`, `~/.claude/settings.json` and `~/.claude/bin/`.
2. `claude plugin marketplace add Levia-Labs/Crepidoma` then
   `claude plugin install crepidoma-core@crepidoma --scope user`.
3. Remove the PreToolUse `raw_read_guard.py` hook from `~/.claude/settings.json`.
4. Reduce `~/.claude/CLAUDE.md` to personal content; delete `~/.claude/bin/digest.py` and
   `~/.claude/bin/raw_read_guard.py`.
```

- [ ] **Step 5: Verify and commit**

Run: `uv run pytest tests/test_templates.py && task sec`
Expected: pass.

```bash
git add templates docs/migration.md tests/test_templates.py
git commit -m "docs: add pillar templates and migration guide"
```

---

### Task 16: README

**Files:**

- Modify: `README.md`

- [ ] **Step 1: Write `README.md`**

````markdown
# Crepidoma

> In classical Greek architecture, crepidoma is the foundation of one or more steps on which
> the superstructure of a building is erected. Usually the crepidoma has three levels,
> especially in Doric temples. However, exceptions are common: For example, the Heraion at
> Olympia features only two steps, and the Olympeion at Agrigento, Sicily has four.
>
> — [Crepidoma, Wikipedia](https://en.wikipedia.org/wiki/Crepidoma)

![Crepidoma, stereobate and stylobate](https://upload.wikimedia.org/wikipedia/commons/3/39/Crepidoma-stereobate-stylobate.svg)

<sub>"[Crepidoma-stereobate-stylobate.svg](https://commons.wikimedia.org/wiki/File:Crepidoma-stereobate-stylobate.svg)"
by Gleb713, licensed [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), via
Wikimedia Commons. Shown unmodified.</sub>

Crepidoma is the stepped base of Levia Labs. Every pillar project stands on it: one source for
LLM directives, Claude Code agents and hooks, commit gates, shared lint, format and security
configs, Taskfiles and process ADRs. Pillars link Crepidoma; nothing is copied.

## Adopt in a pillar

1. Claude Code plugin, in `.claude/settings.json`:

   ```json
   {
     "extraKnownMarketplaces": {
       "crepidoma": { "source": { "source": "github", "repo": "Levia-Labs/Crepidoma" } }
     },
     "enabledPlugins": { "crepidoma-core@crepidoma": true }
   }
   ```

   Each collaborator runs once: `claude plugin install crepidoma-core@crepidoma --scope project`.

2. Taskfiles and configs, as a submodule:

   ```sh
   git submodule add https://github.com/Levia-Labs/Crepidoma .crepidoma
   ```

   ```yaml
   includes:
     claude: .crepidoma/taskfiles/claude
     lint: .crepidoma/taskfiles/lint
   ```

3. Commit gates, in `.pre-commit-config.yaml`:

   ```yaml
   repos:
     - repo: https://github.com/Levia-Labs/Crepidoma
       rev: v0.1.0
       hooks:
         - id: crepidoma-scrub
         - id: crepidoma-long-files
   ```

Full steps, including the third-party plugin list and every shared gate: [docs/migration.md](docs/migration.md).

## Contents

| Path                                 | What                                                                                                                   |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------- |
| `plugins/crepidoma-core/directives/` | Always-on rules, injected at session start                                                                             |
| `plugins/crepidoma-core/agents/`     | Shared subagents                                                                                                       |
| `plugins/crepidoma-core/hooks/`      | SessionStart directives, PreToolUse raw-read guard                                                                     |
| `plugins/crepidoma-core/bin/digest`  | Bounded output digest on PATH in sessions                                                                              |
| `configs/`                           | editorconfig, gitattributes, prettier, eslint, ruff, yamllint, ast-grep, gitleaks, semgrep, zizmor, hadolint, tsconfig |
| `taskfiles/`                         | Shared `claude:` and `lint:` Taskfile namespaces                                                                       |
| `tools/`                             | scrub, ratchet, drift check, denylist, release                                                                         |
| `docs/adr/`                          | Process decisions shared by all pillars                                                                                |
| `templates/`                         | Files a pillar copies once                                                                                             |

## Working on Crepidoma

```sh
task setup      # uv sync + git hooks
task validate   # everything CI runs
task --list     # all tasks
```

## License

Repository content: [MIT](LICENSE). README image: CC BY-SA 4.0, see attribution above.
````

- [ ] **Step 2: Verify and commit**

Run: `task fmt && task sec`
Expected: pass.

```bash
git add README.md
git commit -m "docs: write README with crepidoma origin and adoption steps"
```

---

### Task 17: CI and Dependabot

**Files:**

- Create: `.github/workflows/validate.yml`, `.github/dependabot.yml`

- [ ] **Step 1: Write `.github/workflows/validate.yml`**

```yaml
name: validate

on:
  push:
    branches: [main]
  pull_request:

permissions:
  contents: read

jobs:
  gates:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@v3
      - uses: arduino/setup-task@v2
      - run: uv sync
      - run: npm install --global @anthropic-ai/claude-code
      - run: uv run pre-commit run --all-files --hook-stage pre-push

  semgrep:
    runs-on: ubuntu-latest
    container: semgrep/semgrep
    steps:
      - uses: actions/checkout@v4
        with:
          persist-credentials: false
      - run: semgrep scan --config auto --config configs/semgrep/rules.yml --error

  osv:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          persist-credentials: false
      - uses: google/osv-scanner-action/osv-scanner-action@v1
        with:
          scan-args: --recursive ./
```

- [ ] **Step 2: Pin every `uses:` to a commit SHA**

For each action, run `gh api repos/<owner>/<repo>/commits/<tag> -q .sha` and replace `@<tag>` with `@<sha> # <tag>`. For `google/osv-scanner-action/osv-scanner-action`, query `repos/google/osv-scanner-action`.
Run: `uv run pre-commit run zizmor --all-files && uv run pre-commit run actionlint --all-files`
Expected: both Passed (zizmor flags any unpinned action).

- [ ] **Step 3: Write `.github/dependabot.yml`**

```yaml
version: 2
updates:
  - package-ecosystem: github-actions
    directory: /
    schedule:
      interval: weekly
  - package-ecosystem: uv
    directory: /
    schedule:
      interval: weekly
```

- [ ] **Step 4: Commit**

```bash
git add .github
git commit -m "ci: run full gate, semgrep and osv-scanner; enable dependabot"
```

---

### Task 18: Release tool

**Files:**

- Create: `tools/release.py`
- Test: `tests/test_release.py`
- Modify: `Taskfile.yml` (add `release`)

**Interfaces:**

- Produces: `bump(root: Path, version: str, today: str) -> list[Path]`, `main(argv) -> int` (CLI `VERSION [--dry-run]`; exit 2 on non-semver; never pushes).

- [ ] **Step 1: Write the failing tests**

```python
import json
from pathlib import Path

import release


def setup_repo(root: Path) -> Path:
    manifest = root / "plugins/crepidoma-core/.claude-plugin/plugin.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps({"name": "crepidoma-core", "version": "0.1.0"}), encoding="utf-8"
    )
    (root / "CHANGELOG.md").write_text("# Changelog\n\n## v0.1.0 - 2026-10-20\n", encoding="utf-8")
    return manifest


def test_bump_updates_manifest_and_changelog(tmp_path: Path):
    manifest = setup_repo(tmp_path)
    changed = release.bump(tmp_path, "0.2.0", "2026-11-01")
    assert json.loads(manifest.read_text(encoding="utf-8"))["version"] == "0.2.0"
    changelog = (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8")
    assert changelog.startswith("# Changelog\n\n## v0.2.0 - 2026-11-01\n")
    assert "## v0.1.0" in changelog
    assert len(changed) == 2


def test_main_rejects_non_semver():
    assert release.main(["v1"]) == 2


def test_main_dry_run_touches_nothing(tmp_path: Path, monkeypatch):
    manifest = setup_repo(tmp_path)
    monkeypatch.setattr(release, "ROOT", tmp_path)
    assert release.main(["0.3.0", "--dry-run"]) == 0
    assert json.loads(manifest.read_text(encoding="utf-8"))["version"] == "0.1.0"
```

Run: `uv run pytest tests/test_release.py`
Expected: FAIL, `ModuleNotFoundError: No module named 'release'`

- [ ] **Step 2: Implement `tools/release.py`**

```python
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
MANIFEST = Path("plugins/crepidoma-core/.claude-plugin/plugin.json")
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
HEADER = "# Changelog\n"


def bump(root: Path, version: str, today: str) -> list[Path]:
    manifest = root / MANIFEST
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["version"] = version
    manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    changelog = root / "CHANGELOG.md"
    body = changelog.read_text(encoding="utf-8").removeprefix(HEADER).lstrip("\n")
    changelog.write_text(f"{HEADER}\n## v{version} - {today}\n\n{body}", encoding="utf-8")
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
```

- [ ] **Step 3: Run tests, add task, commit**

Run: `uv run pytest tests/test_release.py`
Expected: `3 passed`

Add to `Taskfile.yml`:

```yaml
release:
  desc: "Bump version, changelog, commit and tag: task release -- 0.2.0"
  cmds:
    - uv run python tools/release.py {{.CLI_ARGS}}
```

```bash
git add tools/release.py tests/test_release.py Taskfile.yml
git commit -m "feat(tools): add release bump and tag"
```

---

### Task 19: Full verification, review, push

- [ ] **Step 1: Full gate**

Run: `task validate`
Expected: every hook Passed, including pytest and plugin-validate.

- [ ] **Step 2: Scrub the whole history of the branch**

Run: `git log --format=%B main..foundation > .local/commit-messages.txt && uv run python tools/scrub_check.py .local/commit-messages.txt`
Expected: no output (commit messages carry only the allowlisted co-author address).

Run: `uv run pre-commit run gitleaks --all-files`
Expected: Passed.

- [ ] **Step 3: Whole-branch review**

Dispatch `feature-dev:code-reviewer` on `git diff main...foundation` with the spec and this plan; receipt at most 10 lines. Fix confirmed findings, rerun Step 1.

- [ ] **Step 4: Ask the user to confirm the public push**

Stop. Report: commit count, test count, conflicts in `.local/merge-conflicts.md`, review result. Wait for explicit confirmation.

- [ ] **Step 5: Push and open PR (after confirmation only)**

```bash
git push -u origin foundation
gh pr create --base main --head foundation --title "Crepidoma foundation" --body-file .local/pr-body.md
```

The PR body ends with `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.

- [ ] **Step 6: Release after merge (after confirmation only)**

Run: `git switch main && git pull && task release -- 0.1.0 && git push origin main v0.1.0`
Note: the manifest is already `0.1.0`; `bump` rewrites it unchanged and adds the changelog entry.

---

### Task 20: Switch user scope to Crepidoma (after Task 19, explicit confirmation)

- [ ] **Step 1: Ask the user to confirm**

This edits `~/.claude/settings.json` and `~/.claude/CLAUDE.md`. Stop and wait for explicit confirmation.

- [ ] **Step 2: Back up**

Run: `mkdir -p ~/.claude/backups/pre-crepidoma-2026-10-20 && cp -r ~/.claude/CLAUDE.md ~/.claude/settings.json ~/.claude/bin ~/.claude/backups/pre-crepidoma-2026-10-20/`
Expected: exit 0.

- [ ] **Step 3: Install plugin at user scope**

Run: `claude plugin marketplace add Levia-Labs/Crepidoma && claude plugin install crepidoma-core@crepidoma --scope user`
Expected: install success message.

- [ ] **Step 4: Remove duplicated user-scope pieces**

1. In `~/.claude/settings.json`, delete the PreToolUse hook entry whose command runs `raw_read_guard.py`.
2. In `~/.claude/CLAUDE.md`, delete the sections now shipped as directives (CARDINAL DIRECTIVE, Tool-first loop, Communication style); keep `@RTK.md` and the graphify section.
3. Delete `~/.claude/bin/digest.py` and `~/.claude/bin/raw_read_guard.py`.

- [ ] **Step 5: Verify in a fresh session**

Run: `claude -p "State the first rule of your communication style in one line."`
Expected: an answer reflecting the injected no-first-person rule. Then `printf 'a\n' | digest` prints `lines 1 bytes 2` inside a Claude Bash call.
