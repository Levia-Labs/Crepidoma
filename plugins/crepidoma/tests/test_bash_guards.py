import json

import hooks
import hooks_bash_guards as guards
import pytest

STDIN = [
    "python -",
    "python3 -",
    "py -",
    "node -",
    "uv run python -",
    "uv run --no-project python3 -",
    "python3 - <<EOF\nprint(1)\nEOF",
    "python <<'EOF'\nprint(1)\nEOF",
    "cat x | python -",
    "python",
    "bash -c 'python3 -'",
    "FOO=1 python -u -",
]
KILL = [
    "taskkill /IM node.exe /F",
    "taskkill /im node.exe",
    "taskkill /F /IM:node.exe",
    "pkill node",
    "pkill -f server",
    "killall python",
    "Stop-Process -Name node",
    "Get-Process node | Stop-Process",
    'powershell -Command "Stop-Process -Name node"',
    "bash -c 'pkill node'",
]
COMMIT = [
    "git commit -m x",
    "git commit",
    "git -C a commit -am x",
    "git commit -m \"$(cat <<'EOF'\nx\nEOF\n)\"",
]
ALLOWED = [
    "python script.py",
    "python script.py -",
    "python -c 'print(1)'",
    "python -m pytest -q",
    "python --version",
    "uv run python script.py",
    "uv run pytest",
    "node -e 'console.log(1)'",
    "node app.js",
    "taskkill /PID 123 /F",
    "kill 123",
    "Stop-Process -Id 123",
    "echo pkill",
    "git status",
    "git add a.py",
    "task git:commit -- 'msg'",
    "cat <<'EOF'\nhello\nEOF",
]


@pytest.mark.parametrize("command", STDIN)
def test_stdin_interpreters_are_refused(command):
    assert "stdin" in guards.bash_refusal(command)


@pytest.mark.parametrize("command", KILL)
def test_kill_by_name_is_refused(command):
    assert "own PID" in guards.bash_refusal(command)


@pytest.mark.parametrize("command", COMMIT)
def test_raw_commit_is_refused(command):
    assert "task git:commit" in guards.bash_refusal(command)


@pytest.mark.parametrize("command", ALLOWED)
def test_safe_commands_pass(command):
    assert guards.bash_refusal(command) == ""


def event(command, agent=None):
    data = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": "."}
    if agent:
        data["agent_id"] = agent
    return data


@pytest.mark.parametrize("agent", [None, "a1"])
def test_pre_bash_applies_to_main_thread_and_subagents(agent, capsys):
    assert hooks.pre_bash(event("pkill node", agent)) == 0
    assert json.loads(capsys.readouterr().out)["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.parametrize("command", ["git add -A", "git add .", "git add --all"])
def test_sweeping_add_is_refused_for_subagents_only(command, capsys):
    hooks.pre_bash(event(command))
    assert capsys.readouterr().out == ""
    hooks.pre_bash(event(command, "a1"))
    assert "deny" in capsys.readouterr().out


def test_pre_bash_lets_a_clean_command_through(capsys):
    assert hooks.pre_bash(event("python script.py", "a1")) == 0
    assert capsys.readouterr().out == ""
