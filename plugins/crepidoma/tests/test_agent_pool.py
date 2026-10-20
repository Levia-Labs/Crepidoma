import json
import random
from datetime import UTC, datetime, timedelta

import agent_pool

NOW = datetime(2026, 10, 21, 12, 0, 0, tzinfo=UTC)


def stamp(seconds_ago: float) -> str:
    return (NOW - timedelta(seconds=seconds_ago)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def make_agent(sub, name, kind, idle, tokens, finished=True):
    sub.mkdir(parents=True, exist_ok=True)
    meta = {"agentType": kind, "finished": finished}
    (sub / f"agent-{name}.meta.json").write_text(json.dumps(meta), encoding="utf-8")
    usage = {
        "input_tokens": 2,
        "cache_creation_input_tokens": tokens - 2,
        "cache_read_input_tokens": 0,
    }
    lines = [
        {"type": "user", "timestamp": stamp(idle + 5)},
        {"type": "assistant", "timestamp": stamp(idle), "message": {"usage": usage}},
        {"type": "user", "timestamp": stamp(idle)},
    ]
    text = "\n".join(json.dumps(line) for line in lines) + "\n"
    (sub / f"agent-{name}.jsonl").write_text(text, encoding="utf-8")


def test_context_tokens_sums_three_fields():
    usage = {"input_tokens": 1, "cache_creation_input_tokens": 20, "cache_read_input_tokens": 300}
    assert agent_pool.context_tokens(usage) == 321
    assert agent_pool.context_tokens({}) == 0


def test_verdict_boundaries():
    assert agent_pool.verdict(10, 100, 300, 40000) == "reuse"
    assert agent_pool.verdict(300, 100, 300, 40000) == "rotate"
    assert agent_pool.verdict(10, 40000, 300, 40000) == "rotate"


def test_verdict_random_matches_definition():
    rng = random.Random(7)  # noqa: S311
    for _ in range(300):
        idle, ctx = rng.uniform(0, 600), rng.randint(0, 80000)
        expect = "reuse" if idle < 300 and ctx < 40000 else "rotate"
        assert agent_pool.verdict(idle, ctx, 300, 40000) == expect


def test_session_dir_name_and_project_dir():
    assert agent_pool.project_slug("D:\\work\\demo") == "D--work-demo"


def test_read_agent_uses_last_usage_and_last_timestamp(tmp_path):
    make_agent(tmp_path, "a1", "crepidoma:implementer", 30, 9000)
    row = agent_pool.read_agent(tmp_path / "agent-a1.jsonl", NOW)
    assert row["id"] == "a1" and row["type"] == "crepidoma:implementer"
    assert row["context"] == 9000 and round(row["idle"]) == 30


def test_read_agent_skips_unfinished_and_garbage(tmp_path):
    make_agent(tmp_path, "a1", "t", 30, 9000, finished=False)
    assert agent_pool.read_agent(tmp_path / "agent-a1.jsonl", NOW) is None
    (tmp_path / "agent-a2.jsonl").write_text("not json\n", encoding="utf-8")
    assert agent_pool.read_agent(tmp_path / "agent-a2.jsonl", NOW) is None


def test_pool_filters_type_and_sorts_by_idle(tmp_path):
    make_agent(tmp_path, "a1", "x", 100, 5000)
    make_agent(tmp_path, "a2", "y", 10, 5000)
    make_agent(tmp_path, "a3", "x", 20, 50000)
    rows = agent_pool.pool(tmp_path, NOW, 300, 40000)
    assert [r["id"] for r in rows] == ["a2", "a3", "a1"]
    assert [r["verdict"] for r in rows] == ["reuse", "rotate", "reuse"]
    assert [r["id"] for r in agent_pool.pool(tmp_path, NOW, 300, 40000, "x")] == ["a3", "a1"]


def test_find_session_newest(tmp_path):
    proj = tmp_path / "projects" / "X--p"
    old, new = proj / "old", proj / "new"
    (old / "subagents").mkdir(parents=True)
    (new / "subagents").mkdir(parents=True)
    import os

    os.utime(old, (1, 1))
    assert agent_pool.find_session(tmp_path / "projects", "X--p", None) == new
    assert agent_pool.find_session(tmp_path / "projects", "X--p", "old") == old
    assert agent_pool.find_session(tmp_path / "projects", "X--p", "nope") is None


def test_decide_denies_with_reason(tmp_path):
    make_agent(tmp_path, "a1", "x", 30, 5000)
    event = {"tool_name": "Agent", "tool_input": {"subagent_type": "x", "description": "job"}}
    out = agent_pool.decide(event, tmp_path, NOW, 300, 40000)
    spec = out["hookSpecificOutput"]
    assert spec["permissionDecision"] == "deny"
    assert spec["permissionDecisionReason"] == (
        "reuse a1 via SendMessage (context 5000 tok, idle 30 s); "
        "start fresh only by putting [fresh] in the description"
    )


def test_decide_allows(tmp_path):
    make_agent(tmp_path, "a1", "x", 30, 5000)
    base = {"tool_name": "Agent", "tool_input": {"subagent_type": "x", "description": "job"}}
    assert agent_pool.decide(base, tmp_path, NOW, 300, 40000) is not None
    fresh = {
        "tool_name": "Agent",
        "tool_input": {"subagent_type": "x", "description": "[fresh] job"},
    }
    assert agent_pool.decide(fresh, tmp_path, NOW, 300, 40000) is None
    other = {"tool_name": "Agent", "tool_input": {"subagent_type": "z", "description": "job"}}
    assert agent_pool.decide(other, tmp_path, NOW, 300, 40000) is None
    sub = {**base, "agent_id": "abc"}
    assert agent_pool.decide(sub, tmp_path, NOW, 300, 40000) is None
    bash = {"tool_name": "Bash", "tool_input": {}}
    assert agent_pool.decide(bash, tmp_path, NOW, 300, 40000) is None
    assert agent_pool.decide({"tool_input": 3}, tmp_path, NOW, 300, 40000) is None


def test_list_command_prints_rows(tmp_path, monkeypatch, capsys):
    proj = tmp_path / "projects" / "slug" / "sess" / "subagents"
    make_agent(proj, "a1", "x", 30, 5000)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(agent_pool, "project_slug", lambda cwd: "slug")
    assert agent_pool.main(["list", "--type", "x"]) == 0
    line = capsys.readouterr().out.strip()
    assert line.startswith("a1 x ")
    assert line.endswith((" reuse", " rotate"))


def test_hook_fails_open(monkeypatch, capsys):
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO("{bad"))
    assert agent_pool.main(["hook"]) == 0
    assert capsys.readouterr().out == ""
