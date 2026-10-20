import json
from pathlib import Path

import pytest
import spend


def assistant(msg_id: str, model: str, usage: dict, blocks: list[dict], ts: str) -> dict:
    return {
        "timestamp": ts,
        "message": {"id": msg_id, "model": model, "usage": usage, "content": blocks},
    }


def user_result(tool_id: str, text: str) -> dict:
    block = {"type": "tool_result", "tool_use_id": tool_id, "content": text}
    return {"message": {"content": [block]}}


def tool_use(tool_id: str, name: str, params: dict) -> dict:
    return {"type": "tool_use", "id": tool_id, "name": name, "input": params}


def write(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    usage = {
        "input_tokens": 1_000_000,
        "output_tokens": 1_000_000,
        "cache_read_input_tokens": 1_000_000,
        "cache_creation_input_tokens": 1_000_000,
    }
    write(
        root / "aaaaaaaa-1111.jsonl",
        [
            assistant(
                "m1",
                "claude-opus-5-5",
                usage,
                [
                    tool_use("t1", "Read", {"file_path": "C:\\src\\big.py"}),
                    tool_use("t2", "Bash", {"command": "sed -n 1,5p src/small.py"}),
                    tool_use("t3", "Bash", {"command": "head -n 5 src/small.py | wc -l"}),
                ],
                "2026-01-02T10:00:00Z",
            ),
            # duplicate entry for the same API response must not be double counted
            assistant("m1", "claude-opus-5-5", usage, [], "2026-01-02T10:00:01Z"),
            user_result("t1", "x" * 500),
            user_result("t2", "y" * 40),
            user_result("t3", "z" * 20),
        ],
    )
    write(
        root / "bbbbbbbb-2222.jsonl",
        [assistant("m2", "claude-haiku-5-5", {"input_tokens": 10}, [], "2026-02-03T10:00:00Z")],
    )
    sub = root / "aaaaaaaa-1111" / "subagents"
    write(
        sub / "agent-abc12345.jsonl",
        [assistant("s1", "claude-sonnet-5-5", {"output_tokens": 100}, [], "2026-01-02T10:05:00Z")],
    )
    (sub / "agent-abc12345.meta.json").write_text(
        json.dumps({"agentType": "scout"}), encoding="utf-8"
    )
    return root


def run(capsys, *argv: str) -> list[str]:
    assert spend.main(list(argv)) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) <= spend.MAX_LINES
    return lines


def test_slug_replaces_non_alphanumerics():
    assert spend.project_slug(Path("/a/b_c")).endswith("a-b-c")


def test_default_dir_uses_project_env(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    assert spend.default_dir() == tmp_path / "home" / ".claude" / "projects" / spend.project_slug(
        tmp_path
    )


def test_missing_dir_is_usage_error(tmp_path, capsys):
    assert spend.main(["cost", "--dir", str(tmp_path / "nope")]) == 2


def test_sessions_lists_id8_date_cost(folder, capsys):
    lines = run(capsys, "sessions", "--dir", str(folder))
    text = "\n".join(lines)
    assert "aaaaaaaa 2026-01-02" in text
    assert "bbbbbbbb 2026-02-03" in text
    # opus 5+25+0.5+6.25 = 36.75, plus sonnet 100 output tokens = 0.0015
    assert "$   36.75" in text


def test_sessions_last(folder, capsys):
    lines = run(capsys, "sessions", "--last", "1", "--dir", str(folder))
    assert lines[0] == "sessions 1/2"
    assert "bbbbbbbb" in lines[1]


def test_tools_ranks_by_bytes(folder, capsys):
    lines = run(capsys, "tools", "--dir", str(folder))
    assert lines[1].startswith("Read")
    assert "500 B" in lines[1]
    assert any(line.startswith("Bash") and "2 calls" in line and "60 B" in line for line in lines)


def test_reads_include_bash_reads(folder, capsys):
    lines = run(capsys, "reads", "--dir", str(folder))
    assert lines[1].endswith("C:/src/big.py")
    assert "500" in lines[1]
    assert any(line.endswith("src/small.py") and "60 B" in line for line in lines)


def test_bash_read_files():
    assert spend.bash_read_files("cat a.txt b.txt > out") == ["a.txt", "b.txt"]
    assert spend.bash_read_files("sed -n 1,5p a.txt") == ["a.txt"]
    assert spend.bash_read_files("ls -la") == []


def test_agents(folder, capsys):
    lines = run(capsys, "agents", "--dir", str(folder))
    assert "scout" in lines[1]
    assert "claude-sonnet-5-5" in lines[1]
    assert "100 tok" in lines[1]


def test_cost_per_model_and_session_filter(folder, capsys):
    lines = run(capsys, "cost", "--dir", str(folder))
    assert "claude-opus-5-5" in lines[1]
    assert "$36.75" in lines[1]
    assert lines[-1].startswith("total $36.75")
    only = run(capsys, "cost", "--session", "bbbb", "--dir", str(folder))
    assert "claude-haiku-5-5" in only[1]
    assert "claude-opus-5-5" not in "\n".join(only)


def test_output_capped_at_twenty_lines(tmp_path, capsys):
    root = tmp_path / "many"
    for i in range(40):
        write(
            root / f"{i:08d}-x.jsonl",
            [
                assistant(
                    f"m{i}", "claude-opus-5-5", {"input_tokens": 1}, [], "2026-03-01T00:00:00Z"
                )
            ],
        )
    lines = run(capsys, "sessions", "--last", "40", "--top", "99", "--dir", str(root))
    assert len(lines) <= spend.MAX_LINES


def test_unknown_model_has_no_price():
    assert spend.model_cost("mystery", spend.Counter(input=5)) == 0.0
