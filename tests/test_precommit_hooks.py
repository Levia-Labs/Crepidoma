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
