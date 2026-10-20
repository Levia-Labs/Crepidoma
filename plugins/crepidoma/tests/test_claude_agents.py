import importlib.util
import json
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "claude" / "agents.py"
spec = importlib.util.spec_from_file_location("claude_agents", SCRIPT)
agents = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = agents
spec.loader.exec_module(agents)


def turn(message_id, blocks, read=100, output=10):
    usage = {"input_tokens": read, "cache_read_input_tokens": 0, "output_tokens": output}
    return {
        "type": "assistant",
        "message": {"id": message_id, "content": blocks, "usage": usage},
    }


def write(path, entries):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\nnot json\n", encoding="utf-8")


def tree(tmp_path, monkeypatch):
    monkeypatch.setattr(agents, "TRANSCRIPTS", tmp_path)
    write(tmp_path / "abcd1234-0000.jsonl", [turn("m0", [{"type": "text", "text": "hi"}], 500)])
    sub = tmp_path / "abcd1234-0000" / "subagents" / "agent-x.jsonl"
    brief = {"type": "user", "message": {"content": "do the thing"}}
    read = {"type": "tool_use", "name": "Read"}
    result = {
        "type": "user",
        "message": {"content": [{"type": "tool_result", "content": "x" * 2048}]},
    }
    write(
        sub,
        [
            brief,
            # One response split over two entries: the usage counts once.
            turn("m1", [read], read=1000),
            turn("m1", [read], read=1000),
            result,
            turn("m2", [{"type": "text", "text": "done"}], read=3000, output=5),
        ],
    )
    meta = {"agentType": "general-purpose", "description": "Fix it", "model": "sonnet"}
    sub.with_suffix(".meta.json").write_text(json.dumps(meta), encoding="utf-8")


def test_cost_counts_a_split_response_once(tmp_path, monkeypatch):
    tree(tmp_path, monkeypatch)
    [agent] = agents.agents()
    cost = agent.cost
    assert cost.turns == 2
    assert cost.context == 1000 + 10 + 3000 + 5
    assert cost.base == 1000
    assert cost.tools["Read"] == 2
    assert cost.results == 2048
    assert cost.prompt == len("do the thing")
    assert cost.reply == len("done")
    assert (agent.kind, agent.session) == ("general-purpose", "abcd1234")


def test_report_names_the_type_and_the_agent(tmp_path, monkeypatch, capsys):
    tree(tmp_path, monkeypatch)
    assert agents.main([]) == 0
    out = capsys.readouterr().out
    assert "1 subagent(s)" in out
    assert "general-purpose / Fix it" in out


def test_sessions_split_main_from_subagents(tmp_path, monkeypatch, capsys):
    tree(tmp_path, monkeypatch)
    assert agents.main(["--sessions"]) == 0
    assert "abcd1234" in capsys.readouterr().out


def test_reads_counts_files_across_agents(tmp_path, monkeypatch, capsys):
    tree(tmp_path, monkeypatch)
    sub = next(tmp_path.rglob("agent-x.jsonl"))
    monkeypatch.setattr(agents, "ROOT", tmp_path / "repo")
    path = str(tmp_path / "repo" / "CLAUDE.md")
    read = {"type": "tool_use", "name": "Read", "input": {"file_path": path}}
    write(sub, [turn("m9", [read, read])])
    assert agents.main(["--reads"]) == 0
    assert capsys.readouterr().out.split() == ["2", "CLAUDE.md"]


def test_json_lists_every_agent(tmp_path, monkeypatch, capsys):
    tree(tmp_path, monkeypatch)
    agents.main(["--json"])
    [row] = json.loads(capsys.readouterr().out)
    assert row["cost"]["turns"] == 2


def test_a_missing_meta_file_is_not_fatal(tmp_path, monkeypatch):
    tree(tmp_path, monkeypatch)
    next(tmp_path.rglob("*.meta.json")).unlink()
    [agent] = agents.agents()
    assert agent.kind == "?"


def test_no_transcripts_is_an_error(tmp_path, monkeypatch):
    monkeypatch.setattr(agents, "TRANSCRIPTS", tmp_path / "absent")
    assert agents.main([]) == 1
