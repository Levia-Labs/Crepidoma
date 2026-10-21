import json
import random
from pathlib import Path

import pytest
import spend
import spend_parse


def write(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")


def calls_entries(prefix: str) -> list[dict]:
    use = [
        {
            "type": "tool_use",
            "id": f"{prefix}1",
            "name": "Bash",
            "input": {"command": "ls " + "x" * 80},
        },
        {"type": "tool_use", "id": f"{prefix}2", "name": "Read", "input": {"file_path": "/a/b.py"}},
    ]
    results = [
        {"type": "tool_result", "tool_use_id": f"{prefix}1", "content": "a" * 300},
        {"type": "tool_result", "tool_use_id": f"{prefix}2", "content": [{"text": "b" * 900}]},
    ]
    return [
        {"timestamp": "2026-01-02T10:00:00Z", "message": {"id": prefix, "content": use}},
        {"message": {"content": results}},
    ]


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    write(
        root / "aaaaaaaa-1111.jsonl",
        [
            calls_entries("s")[0],
            {
                "message": {
                    "content": [{"type": "tool_result", "tool_use_id": "s1", "content": "z"}]
                }
            },
        ],
    )
    write(root / "aaaaaaaa-1111" / "subagents" / "agent-abcd1234.jsonl", calls_entries("g"))
    write(root / "aaaaaaaa-1111" / "subagents" / "agent-ffff9999.jsonl", calls_entries("h")[:1])
    return root


def out(capsys, *argv: str) -> list[str]:
    assert spend.main(list(argv)) == 0
    return capsys.readouterr().out.splitlines()


def test_calls_lists_largest_first_with_clipped_input(folder, capsys):
    lines = out(capsys, "calls", "--dir", str(folder), "--session", "abcd1234", "--top", "5")
    assert lines[1].split()[:3] == ["900", "B", "Read"]
    assert lines[1].endswith("/a/b.py")
    assert lines[2].split()[2] == "Bash"
    assert len(lines[2].split(maxsplit=3)[3]) == spend_parse.SUMMARY_CHARS
    assert lines[-1] == "calls 2"


def test_agent_forms_scope_tools_and_reads(folder, capsys):
    for ident in ("abcd1234", "aaaaaaaa/abcd1234", "aaaaaaaa/agent-abcd1234", "1234"):
        assert out(capsys, "tools", "--dir", str(folder), "--session", ident)[-1] == "total 1,200 B"
        assert out(capsys, "reads", "--dir", str(folder), "--session", ident)[-1] == "total 900 B"


def test_session_prefix_still_covers_session_and_agents(folder, capsys):
    lines = out(capsys, "calls", "--dir", str(folder), "--session", "aaaaaaaa")
    assert lines[-1] == "calls 3"


def test_cost_scopes_to_agent(folder, capsys):
    assert out(capsys, "cost", "--dir", str(folder), "--session", "nomatch")[-1] == "total $0.00"


def test_input_summary_prefers_command_then_path():
    assert spend_parse.input_summary({"command": "ls", "file_path": "/x"}) == "ls"
    assert spend_parse.input_summary({"file_path": "/x"}) == "/x"
    assert spend_parse.input_summary({"other": 1}) == '{"other": 1}'
    assert spend_parse.input_summary({}) == ""


def test_input_summary_never_exceeds_limit():
    rng = random.Random(7)  # noqa: S311
    for _ in range(200):
        params = {
            "".join(rng.choices("abc", k=3)): "".join(rng.choices("xy \t", k=rng.randint(0, 200)))
            for _ in range(rng.randint(0, 4))
        }
        assert len(spend_parse.input_summary(params)) <= spend_parse.SUMMARY_CHARS
