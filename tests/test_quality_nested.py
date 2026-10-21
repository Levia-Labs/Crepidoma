import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUALITY = (ROOT / "taskfiles" / "quality").as_posix()


def dry_run(tmp_path: Path, task: str) -> str:
    """Dry-run `task` from a pillar whose own quality namespace nests the shared one."""
    (tmp_path / "pq").mkdir()
    (tmp_path / "Taskfile.yml").write_text(
        'version: "3"\nincludes:\n  quality: ./pq\n', encoding="utf-8"
    )
    (tmp_path / "pq" / "Taskfile.yml").write_text(
        f'version: "3"\nincludes:\n  shared: {QUALITY}\n'
        "tasks:\n  long-files:\n    cmds: [echo pillar]\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        ["task", "--dry", "--verbose", task],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    return result.stdout + result.stderr


def test_gate_members_resolve_inside_nested_include(tmp_path):
    out = dry_run(tmp_path, "quality:shared:gate")
    assert 'set -- "$@" "quality:shared:$m"' in out


def test_deep_members_resolve_inside_nested_include(tmp_path):
    out = dry_run(tmp_path, "quality:shared:deep")
    assert 'set -- "$@" "quality:shared:$m"' in out
    assert "for m in long-files docs types" in out


def test_top_level_namespace_still_works():
    result = subprocess.run(
        ["task", "--dry", "--verbose", "--taskfile", str(ROOT / "Taskfile.yml"), "quality:gate"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    assert '"quality:$m"' in result.stdout + result.stderr


def test_lint_web_check_skips_the_crepidoma_submodule():
    taskfile = ROOT / "taskfiles" / "lint" / "Taskfile.yml"
    result = subprocess.run(
        ["task", "--dry", "--verbose", "--taskfile", str(taskfile), "web:check"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    assert "!.crepidoma/**" in result.stdout + result.stderr


def test_prettierignore_template_names_the_submodule():
    text = (ROOT / "templates" / ".prettierignore").read_text(encoding="utf-8")
    assert ".crepidoma/" in text.splitlines()
