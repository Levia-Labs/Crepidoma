import os
import subprocess
from pathlib import Path

import pytest

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
        # Matches both {{.TASKFILE_DIR}} and template calls such as (printf "%s/.." .TASKFILE_DIR).
        assert "../" not in text or ".TASKFILE_DIR" in text, taskfile


def test_hooks_check_sends_a_stop_event():
    text = (ROOT / "taskfiles" / "claude" / "Taskfile.yml").read_text(encoding="utf-8")
    assert "hook_event_name" in text
    assert "echo '{}'" not in text


NAMESPACES = (
    "claude",
    "lint",
    "repo",
    "todo",
    "git",
    "graph",
    "test",
    "quality",
    "security",
    "ci",
    "rtk",
    "setup",
)


def test_every_namespace_lists_tasks():
    for namespace in NAMESPACES:
        taskfile = ROOT / "taskfiles" / namespace / "Taskfile.yml"
        assert taskfile.is_file(), namespace
        result = subprocess.run(
            ["task", "--taskfile", str(taskfile), "--list-all"], capture_output=True, text=True
        )
        assert result.returncode == 0, f"{namespace}: {result.stderr[-300:]}"


def test_pillar_can_include_every_namespace(tmp_path):
    lines = ['version: "3"', "includes:"]
    for namespace in NAMESPACES:
        lines.append(f"  {namespace}: {ROOT.as_posix()}/taskfiles/{namespace}")
    (tmp_path / "Taskfile.yml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    result = subprocess.run(["task", "--list-all"], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr[-400:]
    assert "repo:outline" in result.stdout


def test_taskfiles_pass_the_shell_lint():
    result = subprocess.run(
        [
            "uv",
            "run",
            "--no-project",
            "python",
            str(ROOT / "plugins" / "crepidoma" / "scripts" / "taskfile_lint.py"),
            "all",
            *[str(p) for p in sorted((ROOT / "taskfiles").rglob("Taskfile.yml"))],
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout[-600:]


def test_include_vars_override_config_dirs(tmp_path):
    for name, var in (
        ("lint", "LINT_CFG"),
        ("security", "SECURITY_CONFIGS"),
        ("quality", "QUALITY_CONFIGS"),
    ):
        text = (ROOT / "taskfiles" / name / "Taskfile.yml").read_text(encoding="utf-8")
        assert f"{var} | default" in text, var
    (tmp_path / "Taskfile.yml").write_text(
        'version: "3"\nincludes:\n  lint:\n'
        f"    taskfile: {ROOT.as_posix()}/taskfiles/lint\n"
        '    vars: { LINT_CFG: "/pillar/root" }\n',
        encoding="utf-8",
    )
    fake = tmp_path / "bin"
    fake.mkdir()
    (fake / "gitleaks").write_text('#!/bin/sh\necho "ARGS $*"\n', encoding="utf-8")
    (fake / "gitleaks").chmod(0o755)
    env = {**os.environ, "PATH": f"{fake}{os.pathsep}{os.environ['PATH']}"}
    result = subprocess.run(
        ["task", "lint:secrets"], cwd=tmp_path, capture_output=True, text=True, env=env
    )
    assert "/pillar/root/gitleaks.toml" in result.stdout + result.stderr


def test_shared_gitleaks_prefers_root_config():
    for name in ("lint", "security"):
        text = (ROOT / "taskfiles" / name / "Taskfile.yml").read_text(encoding="utf-8")
        assert "[ -f .gitleaks.toml ]" in text, name


def _run_secrets(tmp_path, task, fake_body):
    (tmp_path / "Taskfile.yml").write_text(
        f'version: "3"\nincludes:\n  sec:\n    taskfile: {ROOT.as_posix()}/taskfiles/{task}\n',
        encoding="utf-8",
    )
    fake = tmp_path / "bin"
    fake.mkdir()
    if os.name == "nt":
        (fake / "gitleaks.bat").write_text(fake_body[1], encoding="utf-8")
    else:
        (fake / "gitleaks").write_text(fake_body[0], encoding="utf-8")
        (fake / "gitleaks").chmod(0o755)
    env = {**os.environ, "PATH": f"{fake}{os.pathsep}{os.environ['PATH']}"}
    result = subprocess.run(
        ["task", "sec:secrets"], cwd=tmp_path, capture_output=True, text=True, env=env
    )
    return result.returncode, result.stdout + result.stderr


OLD_GITLEAKS = (
    "#!/bin/sh\n"
    'if [ "$1" = git ]; then echo "unknown command git" >&2; exit 1; fi\n'
    'echo "ARGS $*"\n',
    "@echo off\r\n"
    'if "%1"=="git" (\r\n  echo unknown command git 1>&2\r\n  exit /b 1\r\n)\r\n'
    "echo ARGS %*\r\n",
)
NEW_GITLEAKS = ('#!/bin/sh\necho "ARGS $*"\n', "@echo off\r\necho ARGS %*\r\n")


@pytest.mark.parametrize("task", ["lint", "security"])
def test_gitleaks_falls_back_to_detect(tmp_path, task):
    code, out = _run_secrets(tmp_path, task, OLD_GITLEAKS)
    assert code == 0, out
    assert "ARGS detect --source . --config" in out
    assert "--redact --no-banner" in out


@pytest.mark.parametrize("task", ["lint", "security"])
def test_gitleaks_uses_git_when_supported(tmp_path, task):
    code, out = _run_secrets(tmp_path, task, NEW_GITLEAKS)
    assert code == 0, out
    assert "ARGS git --config" in out
