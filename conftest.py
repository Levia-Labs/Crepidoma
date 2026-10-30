"""Repo-wide pytest setup: isolate every test from the git that launched pytest."""

from __future__ import annotations

import os

import pytest


def git_vars(environ: dict[str, str] | os._Environ[str]) -> list[str]:
    """Names of the GIT_* variables a git hook exports to its children."""
    return [name for name in environ if name.upper().startswith("GIT_")]


@pytest.fixture(autouse=True)
def _isolate_from_outer_git(monkeypatch: pytest.MonkeyPatch) -> None:
    # A pre-push hook run from a linked worktree exports GIT_INDEX_FILE and GIT_DIR as absolute
    # paths, so tests that build throwaway repos in tmp_path committed, tagged and set config in
    # the real repository instead (branch moved, user.name=t, core.hooksPath=.hooks).
    for name in git_vars(os.environ):
        monkeypatch.delenv(name, raising=False)
