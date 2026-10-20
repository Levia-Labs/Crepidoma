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
