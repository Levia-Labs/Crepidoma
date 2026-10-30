import os
import subprocess

from conftest import git_vars


def test_no_git_variable_reaches_a_test():
    assert git_vars(os.environ) == []


def test_git_vars_matches_any_case():
    assert git_vars({"GIT_DIR": "x", "git_index_file": "y", "PATH": "z"}) == [
        "GIT_DIR",
        "git_index_file",
    ]


def test_throwaway_repo_stays_in_tmp_path(tmp_path, monkeypatch):
    outer = tmp_path / "outer"
    inner = tmp_path / "inner"
    for repo in (outer, inner):
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
    # What a hook would export; the autouse fixture runs before this, so restore it by hand
    # and prove a child git honours it, which is why the fixture must strip it.
    monkeypatch.setenv("GIT_DIR", str(outer / ".git"))
    done = subprocess.run(
        ["git", "rev-parse", "--git-dir"], cwd=inner, capture_output=True, text=True, check=True
    )
    assert done.stdout.strip() == str(outer / ".git")
