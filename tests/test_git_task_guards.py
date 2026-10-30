import os
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
GIT_DIR = ROOT / "taskfiles" / "git"
GUARDED = ("status", "head", "log", "files", "commit", "stage")


def init_repo(path: Path) -> Path:
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    return path


def guard(cwd: Path, root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["sh", str(GIT_DIR / "repo_guard.sh"), str(root)],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


@pytest.mark.skipif(shutil.which("sh") is None, reason="needs sh")
def test_guard_passes_same_repo_and_refuses_other(tmp_path):
    a = init_repo(tmp_path / "a")
    b = init_repo(tmp_path / "b")
    (a / "sub").mkdir()
    assert guard(a, a).returncode == 0
    assert guard(a / "sub", a).returncode == 0
    assert guard(b, a).returncode != 0


def test_every_repo_task_has_guard_precondition():
    text = (GIT_DIR / "Taskfile.yml").read_text(encoding="utf-8")
    for name in GUARDED:
        block = re.search(rf"^  {name}:\n(.*?)(?=^  \S|\Z)", text, re.S | re.M).group(1)
        assert "repo_guard.sh" in block, name
        assert "ROOT_DIR" in block and "USER_WORKING_DIR" in block, name
    after = re.search(r"^  after-merge:\n(.*?)(?=^  \S|\Z)", text, re.S | re.M).group(1)
    assert "repo_guard.sh" not in after


def test_commit_retry_survives_cp1250_console(tmp_path):
    driver = tmp_path / "driver.py"
    driver.write_text(
        textwrap.dedent(
            f"""
            import importlib.util, subprocess, sys
            spec = importlib.util.spec_from_file_location("cr", r"{GIT_DIR / "commit_retry.py"}")
            cr = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cr)
            out = "ruff.....Failed\\n- hook id: ruff\\n\\u25cb detail line\\n"
            def fake(args):
                return subprocess.CompletedProcess(args, 1, stdout=out, stderr="")
            cr.run = fake
            raise SystemExit(cr.main(["msg"]))
            """
        ),
        encoding="utf-8",
    )
    env = {**os.environ, "PYTHONIOENCODING": "cp1250"}
    result = subprocess.run([sys.executable, str(driver)], capture_output=True, env=env)
    assert result.returncode == 1, result.stderr
    assert "○".encode() in result.stdout
