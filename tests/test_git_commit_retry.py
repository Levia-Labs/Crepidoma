import importlib.util
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(rel: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


retry = load("taskfiles/git/commit_retry.py", "commit_retry")
stage = load("taskfiles/git/stage_paths.py", "stage_paths")
staged_long = load("taskfiles/quality/staged_long_files.py", "staged_long_files")
failures = load("taskfiles/ci/ci_failures.py", "ci_failures")

FORMATTER = (
    "trim trailing whitespace.....Failed\n"
    "- hook id: trailing-whitespace\n"
    "- files were modified by this hook\n"
)
LINTER = "ruff.....Failed\n- hook id: ruff\n- exit code: 1\n\nx.py:1:1: F401 unused\n"


def test_failed_hooks_formatter_only():
    assert retry.only_formatted(retry.failed_hooks(FORMATTER))
    assert not retry.only_formatted(retry.failed_hooks(LINTER))
    assert not retry.only_formatted(retry.failed_hooks(FORMATTER + LINTER))
    assert not retry.only_formatted([])


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout


def make_repo(tmp_path: Path, hook_body: str) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "t")
    git(repo, "config", "core.hooksPath", ".hooks")
    hooks = repo / ".hooks"
    hooks.mkdir()
    hook = hooks / "pre-commit"
    hook.write_text("#!/bin/sh\n" + hook_body, encoding="utf-8", newline="\n")
    hook.chmod(0o755)
    return repo


# A real hook that strips trailing spaces the first time, like a formatter would.
FORMAT_HOOK = """f=a.txt
if grep -q ' $' "$f"; then
  sed -i 's/ *$//' "$f"
  echo "fmt.....Failed"
  echo "- files were modified by this hook"
  exit 1
fi
"""


def test_retry_commits_after_formatter(tmp_path: Path, monkeypatch, capsys):
    repo = make_repo(tmp_path, FORMAT_HOOK)
    (repo / "a.txt").write_text("hi  \n", encoding="utf-8")
    git(repo, "add", "a.txt")
    monkeypatch.chdir(repo)
    assert retry.commit("msg") == 0
    assert capsys.readouterr().out.startswith("commit ")
    assert git(repo, "show", "HEAD:a.txt") == "hi\n"


def test_other_failure_stops(tmp_path: Path, monkeypatch, capsys):
    repo = make_repo(tmp_path, 'echo "lint.....Failed"\necho "- exit code: 1"\nexit 1\n')
    (repo / "a.txt").write_text("hi\n", encoding="utf-8")
    git(repo, "add", "a.txt")
    monkeypatch.chdir(repo)
    assert retry.commit("msg") != 0
    assert "lint.....Failed" in capsys.readouterr().out
    assert (
        subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True
        ).returncode
        != 0
    )


def test_stage_refuses_unsafe_paths(tmp_path: Path, monkeypatch, capsys):
    repo = make_repo(tmp_path, "exit 0\n")
    (repo / "a.txt").write_text("x\n", encoding="utf-8")
    (repo / "b.txt").write_text("y\n", encoding="utf-8")
    monkeypatch.chdir(repo)
    assert stage.main([]) == 2
    assert stage.main(["."]) == 2
    assert stage.main([str(tmp_path)]) == 2
    assert stage.main(["a.txt"]) == 0
    out = capsys.readouterr().out
    assert "a.txt" in out and "b.txt" not in out
    assert git(repo, "diff", "--cached", "--name-only").split() == ["a.txt"]


def test_staged_long_files(tmp_path: Path, monkeypatch):
    repo = make_repo(tmp_path, "exit 0\n")
    (repo / "big.txt").write_text("x\n" * 5, encoding="utf-8")
    (repo / "small.txt").write_text("x\n", encoding="utf-8")
    (repo / "uv.lock").write_text("x\n" * 5, encoding="utf-8")
    git(repo, "add", "-A")
    monkeypatch.chdir(repo)
    assert staged_long.over_cap(staged_long.staged_files(), 3) == ["big.txt: 5 lines > 3"]


def test_ci_filter_dedupes_and_caps():
    log = "\n".join(
        [
            "job\tstep\t2026-01-01T00:00:00.1Z FAILED tests/test_a.py::test_x - assert 1 == 2",
            "job\tstep\t2026-01-01T00:00:00.2Z FAILED tests/test_a.py::test_x - assert 1 == 2",
            "job\tstep\t2026-01-01T00:00:00.3Z noise line",
            "job\tstep\tsrc/a.go:12:3: undefined: foo",
        ]
        + [f"job\tstep\terror number {i}" for i in range(60)]
    )
    out = failures.filter_log(log)
    assert out[0] == "FAILED tests/test_a.py::test_x - assert 1 == 2"
    assert out[1] == "src/a.go:12:3: undefined: foo"
    assert len(out) == 40 and "noise line" not in out
