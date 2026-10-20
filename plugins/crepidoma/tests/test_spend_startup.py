import argparse
import json
import random
from pathlib import Path

import spend
import spend_startup


def write(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")


def agent_entries(extra: int = 0) -> list[dict]:
    usage = {"input_tokens": 2, "cache_creation_input_tokens": 100, "cache_read_input_tokens": 30}
    return [
        {"type": "user"},
        {
            "type": "attachment",
            "attachment": {"type": "hook_additional_context", "content": ["abcde"]},
        },
        {"type": "attachment", "attachment": {"type": "environment", "snapshot": {"a": "b"}}},
        {"type": "attachment", "attachment": {"type": "prompt_snapshot", "systemPrompt": ["xyz"]}},
        {"type": "attachment", "attachment": {"type": "date", "date": "2026-01-01"}},
        {
            "type": "assistant",
            "message": {"model": "claude-sonnet-x", "usage": usage, "content": []},
        },
        {"type": "assistant", "message": {"model": "other", "usage": {"input_tokens": 999}}},
        *[
            {"type": "attachment", "attachment": {"type": "environment", "snapshot": "q"}}
            for _ in range(extra)
        ],
    ]


def test_first_turn_tokens_and_sizes(tmp_path: Path) -> None:
    f = tmp_path / "agent-1.jsonl"
    write(f, agent_entries())
    row = spend_startup.startup_row(f, "s/1", "Explore")
    assert row.tokens == 132
    assert row.model == "claude-sonnet-x"
    assert row.sizes["hook_additional_context"] == len(json.dumps(["abcde"]))
    assert row.sizes["prompt_snapshot"] == len(json.dumps(["xyz"]))
    assert row.sizes["environment"] == len(json.dumps({"snapshot": {"a": "b"}}))
    assert "date" not in row.sizes


def test_attachments_after_first_turn_ignored(tmp_path: Path) -> None:
    f = tmp_path / "agent-1.jsonl"
    write(f, agent_entries(extra=3))
    assert spend_startup.startup_row(f, "s/1", "x").sizes["environment"] == len(
        '{"snapshot": {"a": "b"}}'
    )


def test_missing_file_is_empty_row(tmp_path: Path) -> None:
    row = spend_startup.startup_row(tmp_path / "none.jsonl", "s/1", "x")
    assert row.tokens == 0 and row.sizes == {}


def test_first_turn_tokens_sums_usage() -> None:
    rng = random.Random(7)  # noqa: S311
    for _ in range(100):
        values = [rng.randint(0, 10**6) for _ in range(rng.randint(0, 3))]
        usage = dict(zip(spend_startup.USAGE, values, strict=False))
        assert spend_startup.first_turn_tokens(usage) == sum(values)


def test_cmd_startup(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    (root).mkdir()
    (root / "aaaaaaaa-1.jsonl").write_text("{}\n", encoding="utf-8")
    write(root / "aaaaaaaa-1" / "subagents" / "agent-abc12345.jsonl", agent_entries())
    (root / "aaaaaaaa-1" / "subagents" / "agent-abc12345.meta.json").write_text(
        json.dumps({"agentType": "Explore"}), encoding="utf-8"
    )
    args = argparse.Namespace(session="aaaaaaaa", top=5)
    lines = spend_startup.cmd_startup(root, args)
    assert any("Explore" in line and "132" in line for line in lines)
    assert lines[-1].startswith("agents 1 first-turn 132")
    args.session = "aaaaaaaa/abc12345"
    assert spend_startup.cmd_startup(root, args)[-1].startswith("agents 1")
    args.session = "zzzz"
    assert spend_startup.cmd_startup(root, args)[-1].startswith("agents 0")


def test_registered_in_spend() -> None:
    assert "startup" in spend.COMMANDS
    spend.build_parser().parse_args(["startup", "--session", "x"])
