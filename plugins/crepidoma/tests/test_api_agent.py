import json
import os
from types import SimpleNamespace

import api_agent
import api_balance
import pytest

KEY = "sk-ant-api03-SECRETKEY"


class FakeOptions:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def result(subtype="success", text="a\nb", error=False):
    return SimpleNamespace(
        subtype=subtype,
        is_error=error,
        num_turns=3,
        total_cost_usd=1.25,
        result=text,
        session_id="s1",
    )


def fake_query(final, seen=None):
    async def query(prompt, options):
        if seen is not None:
            seen.update(prompt=prompt, options=options)
        yield SimpleNamespace(content="noise")
        yield final

    return query


@pytest.fixture
def setup(tmp_path, monkeypatch):
    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "scout.md").write_text(
        "---\nname: scout\ntools: Read, Grep\nmodel: haiku\n---\n\nBody prompt.\n", encoding="utf-8"
    )
    (agents / "plain.md").write_text("---\nname: plain\n---\nHi\n", encoding="utf-8")
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    monkeypatch.setenv("CREPIDOMA_API_LEDGER", str(tmp_path / "l.jsonl"))
    monkeypatch.delenv("ANTHROPIC_ADMIN_KEY", raising=False)
    monkeypatch.delenv("CREPIDOMA_API_CYCLE_START", raising=False)
    return agents


def run(setup, final=None, extra=(), seen=None):
    argv = ["--agent", "scout", "--brief", "do it", "--cwd", "somewhere", *extra]
    return api_agent.main(
        argv,
        query=fake_query(final or result(), seen),
        options_cls=FakeOptions,
        agents_dir=setup,
        opener=None,
    )


def test_parse_and_load_agent(setup):
    agent = api_agent.load_agent("scout", setup)
    assert agent == {"tools": ["Read", "Grep"], "model": "haiku", "prompt": "Body prompt."}
    plain = api_agent.load_agent("plain", setup)
    assert plain["model"] == "sonnet" and plain["tools"] == []


def test_parse_agent_without_frontmatter():
    assert api_agent.parse_agent("just text\n") == ({}, "just text")


def test_scrub_env():
    env = {"CLAUDE_CODE_OAUTH_TOKEN": "x", "ANTHROPIC_AUTH_TOKEN": "y", "KEEP": "1"}
    api_agent.scrub_env(env)
    assert env == {"KEEP": "1"}


def test_run_scrubs_and_builds_options(setup, monkeypatch, capsys):
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "tok")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "tok")
    seen = {}
    assert run(setup, seen=seen) == 0
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in os.environ
    assert "ANTHROPIC_AUTH_TOKEN" not in os.environ
    opts = seen["options"]
    assert seen["prompt"] == "do it"
    assert opts.model == "haiku" and opts.cwd == "somewhere"
    assert opts.allowed_tools == ["Read", "Grep"]
    for rule in ("Bash(git push*)", "Bash(gh pr merge*)", "Bash(git reset --hard*)"):
        assert rule in opts.disallowed_tools
    assert opts.permission_mode == "dontAsk"
    assert opts.max_budget_usd == 2.0 and opts.max_turns == 60
    assert opts.setting_sources == []
    assert opts.system_prompt == "Body prompt."
    assert KEY not in capsys.readouterr().out


def test_bare_bash_becomes_a_scoped_allowlist():
    # A prefix denylist under auto-approved Bash is bypassable (git -C x push, sh -c ...),
    # so unrestricted Bash is never granted; only listed command prefixes run.
    tools = api_agent.scoped_tools(["Read", "Bash", "Edit"])
    assert "Bash" not in tools
    assert tools[:2] == ["Read", "Edit"]
    assert all(t.startswith("Bash(") for t in tools[2:])
    assert "Bash(task:*)" in tools


def test_publishing_tasks_are_denied():
    for rule in ("Bash(task git:commit:*)", "Bash(task git:land:*)", "Bash(task release:*)"):
        assert rule in api_agent.DENY


def test_project_settings_are_opt_in(setup):
    seen = {}
    assert run(setup, seen=seen, extra=["--project-settings"]) == 0
    assert seen["options"].setting_sources == ["project"]


def test_model_override(setup):
    seen = {}
    run(setup, extra=["--model", "opus"], seen=seen)
    assert seen["options"].model == "opus"


def test_ledger_append(setup, tmp_path):
    run(setup)
    run(setup)
    rows = api_balance.read_ledger(tmp_path / "l.jsonl")
    assert len(rows) == 2
    row = rows[0]
    assert {"ts", "agent", "model", "subtype", "turns", "cost_usd", "session_id", "cwd"} <= set(row)
    assert row["agent"] == "scout" and row["cost_usd"] == 1.25 and row["session_id"] == "s1"
    json.dumps(row)


def test_receipt_capped_and_lists_remaining(setup, capsys):
    run(setup, final=result(text="\n".join(f"line{i}" for i in range(50))))
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) <= 10
    assert lines[0] == "subtype: success"
    assert lines[3].startswith("remaining: $198.75")
    assert lines[-1] == "line49"


def test_receipt_unknown_remaining():
    out = api_agent.receipt(result(), None)
    assert out[3] == "remaining: unknown"


def test_error_result_exit_one(setup):
    assert run(setup, final=result("error_max_turns", error=True)) == 1


def test_refuse_without_key(setup, monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    assert run(setup) == 1
    assert not (tmp_path / "l.jsonl").exists()


def test_refuse_under_floor(setup, monkeypatch, tmp_path):
    monkeypatch.setenv("CREPIDOMA_API_CYCLE_START", "2000-01-01")
    api_balance.append_ledger(
        tmp_path / "l.jsonl", {"ts": "2030-01-01T00:00:00", "agent": "a", "cost_usd": 195}
    )
    seen = {}
    assert run(setup, seen=seen) == 3
    assert seen == {}


def test_unknown_agent_is_two(setup):
    argv = ["--agent", "nope", "--brief", "x"]
    assert (
        api_agent.main(
            argv, query=fake_query(result()), options_cls=FakeOptions, agents_dir=setup, opener=None
        )
        == 2
    )


def test_usage_errors_are_two():
    assert api_agent.main(["--agent", "scout"]) == 2


def test_brief_file(setup, tmp_path):
    brief = tmp_path / "b.txt"
    brief.write_text("from file", encoding="utf-8")
    seen = {}
    argv = ["--agent", "scout", "--brief-file", str(brief)]
    api_agent.main(
        argv,
        query=fake_query(result(), seen),
        options_cls=FakeOptions,
        agents_dir=setup,
        opener=None,
    )
    assert seen["prompt"] == "from file"
