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
