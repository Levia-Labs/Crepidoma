import io
import json

import raw_read_guard as guard


def read(limit=None, path="notes.py", agent=None):
    data = {"tool_name": "Read", "tool_input": {"file_path": path}}
    if limit is not None:
        data["tool_input"]["limit"] = limit
    if agent:
        data["agent_id"] = agent
    return data


def bash(command):
    return {"tool_name": "Bash", "tool_input": {"command": command}}


def test_subagent_always_allowed():
    assert guard.decide(read(agent="a1")) is None


def test_read_needs_small_limit():
    assert guard.decide(read()) is not None
    assert guard.decide(read(limit=200)) is not None
    assert guard.decide(read(limit=20)) is None


def test_images_allowed():
    assert guard.decide(read(path="shot.PNG")) is None


def test_bash_raw_reads_denied():
    assert guard.decide(bash("cat README.md")) is not None
    assert guard.decide(bash("head -n 40 README.md")) is not None


def test_bash_plain_commands_allowed():
    assert guard.decide(bash("git status")) is None


def test_plugin_digest_is_a_sink():
    assert guard.decide(bash("cat README.md | digest")) is None
    assert guard.decide(bash("cat README.md | digest --tail 5")) is None


def test_reason_points_at_plugin_digest():
    assert "digest" in guard.decide(read())
    assert "~/.claude/bin" not in guard.decide(read())


def test_malformed_stdin_fails_open(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("not json"))
    assert guard.main() == 0
    assert capsys.readouterr().out == ""


def test_denial_contract(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(read())))
    assert guard.main() == 0
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
