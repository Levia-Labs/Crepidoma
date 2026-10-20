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


def sub_bash(command, cwd=""):
    data = bash(command)
    data["agent_id"] = "a1"
    data["cwd"] = str(cwd)
    return data


def test_subagent_read_cap_is_80():
    assert guard.decide(read(agent="a1")) is not None
    assert guard.decide(read(limit=81, agent="a1")) is not None
    assert guard.decide(read(limit=80, agent="a1")) is None
    assert guard.decide(read(limit=40)) is not None


def test_subagent_refusal_names_cap_and_alternatives():
    text = guard.decide(read(limit=500, agent="a1"))
    assert "80" in text and "4096" in text
    for name in ("digest", "offset", "repo:outline", "repo:section"):
        assert name in text


def test_subagent_sed_head_tail_caps():
    assert guard.decide(sub_bash("sed -n 60,240p CLAUDE.md")) is not None
    assert guard.decide(sub_bash("sed -n 60,139p CLAUDE.md")) is None
    assert guard.decide(sub_bash("head -n 81 a.md")) is not None
    assert guard.decide(sub_bash("tail -n 80 a.md")) is None
    assert guard.decide(sub_bash("head -c 5000 a.md")) is not None
    assert guard.decide(sub_bash("head -c 4096 a.md")) is None


def test_subagent_cat_by_file_size(tmp_path):
    (tmp_path / "big.yml").write_text("x" * 5000, encoding="utf-8")
    (tmp_path / "small.yml").write_text("a: 1\n", encoding="utf-8")
    (tmp_path / "long.txt").write_text("l\n" * 100, encoding="utf-8")
    assert guard.decide(sub_bash("cat big.yml", tmp_path)) is not None
    assert guard.decide(sub_bash("cat small.yml", tmp_path)) is None
    assert guard.decide(sub_bash("cat big.yml | digest", tmp_path)) is None
    assert guard.decide(sub_bash("cat long.txt", tmp_path)) is not None


def test_subagent_task_output_by_size(tmp_path):
    out = tmp_path / "tasks" / "b1.output"
    out.parent.mkdir()
    out.write_text("y" * 5000, encoding="utf-8")
    assert guard.decide(sub_bash(f"cat {out.as_posix()}")) is not None
    out.write_text("ok\n", encoding="utf-8")
    assert guard.decide(sub_bash(f"cat {out.as_posix()}")) is None


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
