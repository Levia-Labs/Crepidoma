"""Pushing is main-thread only: settings no longer deny it, so the subagent Bash hook must."""

import hooks
import pytest


def untracked(_path, _root):
    return False


@pytest.mark.parametrize(
    ("command", "refused"),
    [
        ("git push", True),
        ("git push -u origin feat/x", True),
        ("git -C ../pillar push origin main", True),
        ("rtk git push", True),
        ("git log origin/main..HEAD", False),
        ("git remote -v", False),
    ],
)
def test_subagents_cannot_push(tmp_path, command, refused):
    assert bool(hooks.inner_refusal(command, tmp_path, untracked)) is refused


def test_subagent_push_is_denied_by_the_bash_hook(tmp_path, capsys):
    event = {"tool_name": "Bash", "agent_id": "a1", "cwd": str(tmp_path)}
    event["tool_input"] = {"command": "git push -u origin feat/x"}
    hooks.pre_bash(event)
    assert '"permissionDecision": "deny"' in capsys.readouterr().out


def test_main_thread_push_passes_the_bash_hook(capsys):
    event = {"tool_name": "Bash", "tool_input": {"command": "git push"}}
    assert hooks.pre_bash(event) == 0
    assert capsys.readouterr().out == ""
