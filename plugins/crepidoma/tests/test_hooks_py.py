"""hooks.py: gates, the agent dispatch policy, the git guard and the CLI contract."""

import io
import json
import subprocess
import sys
import time
from pathlib import Path

import hooks
import pytest


@pytest.fixture(autouse=True)
def opted_in(request, monkeypatch):
    """Ported tests assume a pillar that adopted Crepidoma; opt-in tests mark themselves."""
    if "no_opt_in" not in request.keywords:
        monkeypatch.setattr(hooks, "opted_in", lambda: True)


def write_settings(root, plugins):
    settings = root / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(json.dumps({"enabledPlugins": plugins}), encoding="utf-8")


@pytest.mark.no_opt_in
def test_opt_in_requires_project_enabled_plugin(tmp_path, monkeypatch):
    monkeypatch.setattr(hooks, "ROOT", tmp_path)
    assert hooks.opted_in() is False
    write_settings(tmp_path, {"crepidoma@levia-labs": False})
    assert hooks.opted_in() is False
    write_settings(tmp_path, {"crepidoma@levia-labs": True})
    assert hooks.opted_in() is True


@pytest.mark.no_opt_in
def test_malformed_settings_is_not_opt_in(tmp_path, monkeypatch):
    monkeypatch.setattr(hooks, "ROOT", tmp_path)
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.json").write_text("{not json", encoding="utf-8")
    assert hooks.opted_in() is False


@pytest.mark.no_opt_in
def test_stop_runs_no_project_code_without_opt_in(tmp_path, monkeypatch):
    monkeypatch.setattr(hooks, "ROOT", tmp_path)
    marker = tmp_path / "dirty"
    marker.write_text("", encoding="utf-8")
    gate = hooks.GATES[0]._replace(marker=marker)
    monkeypatch.setattr(hooks, "GATES", (gate,))
    calls = []
    monkeypatch.setattr(hooks, "run", lambda *args, **kw: calls.append(args))
    assert hooks.stop({}) == 0
    assert calls == []


@pytest.mark.no_opt_in
def test_project_budget_script_never_preferred_over_plugin(tmp_path, monkeypatch):
    monkeypatch.setattr(hooks, "ROOT", tmp_path)
    script = tmp_path / hooks.BUDGET_SCRIPTS[0]
    script.parent.mkdir(parents=True)
    script.write_text("", encoding="utf-8")
    assert hooks.budget_script() != script


NAMED = {"subagent_type": "toolsmith", "model": "sonnet"}
AGENT = {"tool_name": "Agent", "tool_input": NAMED}
CHECK_SUFFIXES = (".yml", ".yaml", ".py", ".md", ".sh", ".toml")
CHECK_SKIP = (
    "tasks/projects/templates/",
    "graphify-out/",
    "reports/",
    ".claude/skills/",
    ".claude/marketplace/",
)


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.setattr(hooks, "ROOT", root)
    monkeypatch.setattr(hooks, "USAGE_CACHE", tmp_path / "usage.json")
    monkeypatch.setattr(hooks, "LEDGER", tmp_path / "lanes.json")
    monkeypatch.setattr(hooks, "PLUGIN_AGENTS", tmp_path / "plugin-agents")
    gates = tuple(gate._replace(marker=tmp_path / gate.marker.name) for gate in hooks.GATES)
    monkeypatch.setattr(hooks, "GATES", gates)
    return root


def check_gate(marker):
    return hooks.Gate(marker, "", CHECK_SUFFIXES, ("check",), (), CHECK_SKIP)


def completed(code, out=""):
    return subprocess.CompletedProcess(args="", returncode=code, stdout=out, stderr="")


def agent(subagent_type=None, model="sonnet"):
    arguments = {"prompt": "x", "model": model}
    if subagent_type is not None:
        arguments["subagent_type"] = subagent_type
    return {"tool_name": "Agent", "tool_input": arguments}


def decision(capsys):
    return json.loads(capsys.readouterr().out)["hookSpecificOutput"]


# ---- Ported: single check gate -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("tasks/lint/Taskfile.yml", True),
        ("tasks/quality/docs.py", True),
        ("CLAUDE.md", True),
        ("pyproject.toml", True),
        ("sgconfig.yml", True),
        ("tasks/projects/templates/flask/app/app.py", False),
        ("graphify-out/graph.json", False),
        ("assets/icon.png", False),
    ],
)
def test_in_scope(tmp_path, path, expected):
    assert hooks.in_scope(path, check_gate(tmp_path / "m")) is expected


def test_in_scope_accepts_an_absolute_path(tmp_path):
    path = str(hooks.ROOT / "tasks" / "lint" / "Taskfile.yml")
    assert hooks.in_scope(path, check_gate(tmp_path / "m"))


@pytest.fixture
def dirty(monkeypatch, tmp_path):
    marker = tmp_path / "check-dirty"
    marker.touch()
    monkeypatch.setattr(hooks, "GATES", (check_gate(marker),))
    return marker


def fake(monkeypatch, returncode, output):
    calls = []

    def run(*command):
        calls.append(command)
        return subprocess.CompletedProcess(command, returncode, output, "")

    monkeypatch.setattr(hooks, "run", run)
    return calls


def test_stop_runs_the_fast_tier_and_clears_the_marker(monkeypatch, dirty):
    calls = fake(monkeypatch, 0, "")
    assert hooks.stop({}) == 0
    assert calls[0] == ("task", "check")
    assert not dirty.exists()


def test_stop_blocks_on_a_failing_gate(monkeypatch, dirty, capsys):
    fake(monkeypatch, 1, "tests/x.py::test_y FAILED")
    hooks.stop({})
    result = json.loads(capsys.readouterr().out)
    assert result["decision"] == "block"
    assert "task check failed" in result["reason"]
    assert dirty.exists()


def test_stop_skips_when_the_gate_cannot_run(monkeypatch, dirty, capsys):
    fake(monkeypatch, 127, "error: Failed to spawn: `pytest`")
    hooks.stop({})
    result = json.loads(capsys.readouterr().out)
    assert "decision" not in result
    assert "task check" in result["systemMessage"]
    assert dirty.exists()


def test_run_reports_a_missing_executable_as_127():
    result = hooks.run("no-such-binary-xyz", "check")
    assert result.returncode == 127
    assert "executable file not found" in result.stderr


def test_stop_skips_when_uv_is_missing_under_task(monkeypatch, dirty, capsys):
    fake(monkeypatch, 1, 'task: "uv": executable file not found in $PATH')
    hooks.stop({})
    result = json.loads(capsys.readouterr().out)
    assert "decision" not in result
    assert "systemMessage" in result
    assert dirty.exists()


def test_stop_blocks_a_real_failure_whose_output_mentions_a_skip_reason(monkeypatch, dirty, capsys):
    output = "\n".join(
        [
            "captured stdout: error: Failed to spawn: `x`",
            "FAILED tests/x.py::test_y - AssertionError",
            "1 failed, 89 passed in 2.1s",
            'task: Failed to run task "check": exit status 1',
        ]
    )
    fake(monkeypatch, 1, output)
    hooks.stop({})
    assert json.loads(capsys.readouterr().out)["decision"] == "block"
    assert dirty.exists()


def test_stop_blocks_when_a_failed_line_in_the_tail_quotes_a_skip_reason(
    monkeypatch, dirty, capsys
):
    output = "\n".join(
        [
            "FAILED tests/x.py::test_y - AssertionError: executable file not found",
            "1 failed in 0.1s",
            'task: Failed to run task "check": exit status 1',
        ]
    )
    fake(monkeypatch, 1, output)
    hooks.stop({})
    assert json.loads(capsys.readouterr().out)["decision"] == "block"
    assert dirty.exists()


def test_stop_blocks_when_a_pytest_error_line_in_the_tail_quotes_a_skip_reason(
    monkeypatch, dirty, capsys
):
    output = "\n".join(
        [
            "E   AssertionError: executable file not found",
            "1 failed in 0.1s",
            'task: Failed to run task "check": exit status 1',
        ]
    )
    fake(monkeypatch, 1, output)
    hooks.stop({})
    assert json.loads(capsys.readouterr().out)["decision"] == "block"
    assert dirty.exists()


@pytest.mark.parametrize(
    "subagent_type", [None, "", "  ", "general-purpose", "claude", "fork", "Explore", "Plan"]
)
def test_pre_tool_use_refuses_a_catch_all_agent(monkeypatch, capsys, subagent_type):
    # The policy is checked before the allowance: no usage reading is needed to refuse.
    monkeypatch.setattr(hooks, "usage_reading", lambda: pytest.fail("read the allowance"))
    hooks.pre_tool_use(agent(subagent_type))
    result = decision(capsys)
    assert result["permissionDecision"] == "deny"
    assert ".claude/agents/" in result["permissionDecisionReason"]


@pytest.mark.parametrize("subagent_type", ["toolsmith", "caveman:cavecrew-builder", "explorer"])
def test_pre_tool_use_lets_a_named_agent_through(monkeypatch, capsys, subagent_type):
    monkeypatch.setattr(hooks, "usage_reading", dict)
    assert hooks.pre_tool_use(agent(subagent_type)) == 0
    assert capsys.readouterr().out == ""


def test_pre_tool_use_refuses_a_named_agent_at_the_ceiling(monkeypatch, capsys):
    reading = {
        "over_ceiling": True,
        "wait_seconds": 600,
        "windows": [{"label": "Session (5 hour)", "utilization": 97.0}],
    }
    monkeypatch.setattr(hooks, "usage_reading", lambda: reading)
    hooks.pre_tool_use(agent("toolsmith"))
    result = decision(capsys)
    assert result["permissionDecision"] == "deny"
    assert "97%" in result["permissionDecisionReason"]


def lanes(tmp_path, finished, count):
    folder = tmp_path / "session" / "subagents"
    folder.mkdir(parents=True, exist_ok=True)
    for n in range(count):
        meta = {"agentType": "toolsmith", "finished": finished}
        (folder / f"agent-{finished}-{n}.meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return str(tmp_path / "session.jsonl")


def test_running_agents_counts_only_unfinished_lanes(tmp_path):
    lanes(tmp_path, True, 4)
    transcript = lanes(tmp_path, False, 2)
    assert hooks.running_agents(transcript, time.time()) == 2


def test_running_agents_ignores_a_stale_lane(tmp_path, monkeypatch):
    transcript = lanes(tmp_path, False, 2)
    monkeypatch.setattr(hooks, "RUNNING_SECONDS", -1)
    assert hooks.running_agents(transcript, time.time()) == 0


def test_running_agents_without_a_transcript_is_zero():
    assert hooks.running_agents("", time.time()) == 0


def test_pre_tool_use_refuses_a_seventh_agent(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(hooks, "usage_reading", dict)
    event = agent("toolsmith")
    event["transcript_path"] = lanes(tmp_path, False, hooks.MAX_AGENTS)
    hooks.pre_tool_use(event)
    result = decision(capsys)
    assert result["permissionDecision"] == "deny"
    assert "already running" in result["permissionDecisionReason"]


def test_pre_tool_use_ignores_bash(monkeypatch, capsys):
    monkeypatch.setattr(hooks, "usage_reading", lambda: pytest.fail("read the allowance"))
    assert hooks.pre_tool_use({"tool_name": "Bash", "tool_input": {}}) == 0
    assert capsys.readouterr().out == ""


def test_stop_does_nothing_when_clean(monkeypatch):
    calls = fake(monkeypatch, 0, "")
    assert hooks.stop({}) == 0
    assert calls == []


# ---- Ported: two-gate configuration ----------------------------------------------------


@pytest.fixture
def gates(tmp_path, monkeypatch):
    patched = (
        hooks.Gate(
            tmp_path / "claude-ts-dirty",
            "src/",
            (".ts", ".tsx"),
            ("npm:typecheck", "lint:es"),
            (".ts", ".tsx"),
            (),
        ),
        hooks.Gate(tmp_path / "claude-py-dirty", "Tasks/", (".py",), ("py:check",), (".py:",), ()),
    )
    monkeypatch.setattr(hooks, "GATES", patched)
    return patched


def edit(path):
    hooks.post_tool_use({"tool_input": {"file_path": path}})


def test_typescript_edit_marks_only_typescript(gates):
    edit("X:\\repo\\src\\components\\a.tsx")
    assert [gate.marker.exists() for gate in gates] == [True, False]


def test_python_edit_marks_only_python(gates):
    edit("/repo/Tasks/claude/hooks.py")
    assert [gate.marker.exists() for gate in gates] == [False, True]


def test_docs_edit_marks_nothing(gates):
    edit("/repo/src/vite/README.md")
    edit("/repo/vite.config.ts")
    assert not any(gate.marker.exists() for gate in gates)


def test_stop_without_dirty_runs_nothing(gates, monkeypatch):
    monkeypatch.setattr(hooks, "run", lambda *a: pytest.fail(f"ran {a}"))
    assert hooks.stop({}) == 0


def test_stop_blocks_on_failure_and_keeps_marker(gates, monkeypatch, capsys):
    gates[1].marker.touch()
    monkeypatch.setattr(
        hooks, "run", lambda *a: completed(1, "noise\nTasks/x.py:3:1: F401 unused\n")
    )
    assert hooks.stop({}) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["decision"] == "block"
    assert "task py:check failed" in result["reason"]
    assert "F401" in result["reason"]
    assert "noise" not in result["reason"]
    assert gates[1].marker.exists()


def test_stop_clears_markers_when_gates_pass(gates, monkeypatch, capsys):
    for gate in gates:
        gate.marker.touch()
    ran = []
    monkeypatch.setattr(hooks, "run", lambda *a: ran.append(a) or completed(0))
    monkeypatch.setattr(hooks, "usage_reading", dict)
    assert hooks.stop({}) == 0
    assert capsys.readouterr().out == ""
    assert not any(gate.marker.exists() for gate in gates)
    assert ("task", "lint:es") in ran
    assert ("task", "py:check") in ran
    assert ran[-1] == ("graphify", "update", ".", "--force")


def test_stop_reentry_does_nothing(gates, monkeypatch):
    gates[0].marker.touch()
    monkeypatch.setattr(hooks, "run", lambda *a: pytest.fail("ran"))
    assert hooks.stop({"stop_hook_active": True}) == 0


def test_pre_tool_use_denies_agent_over_ceiling(monkeypatch, capsys):
    reading = {
        "over_ceiling": True,
        "wait_seconds": 3720,
        "windows": [{"label": "Session", "utilization": 97.0}],
    }
    monkeypatch.setattr(hooks, "usage_reading", lambda: reading)
    assert hooks.pre_tool_use(AGENT) == 0
    result = decision(capsys)
    assert result["permissionDecision"] == "deny"
    assert "Session at 97%" in result["permissionDecisionReason"]
    assert "1h 2m" in result["permissionDecisionReason"]


def test_pre_tool_use_ignores_other_tools(monkeypatch):
    monkeypatch.setattr(hooks, "usage_reading", lambda: pytest.fail("read usage"))
    assert hooks.pre_tool_use({"tool_name": "Edit"}) == 0


@pytest.mark.parametrize("seconds", [0, 59, 60, 3599, 3600, 3720, 86399, 10**7])
def test_span_formats_hours_and_minutes(seconds):
    hours, rest = divmod(seconds, 3600)
    assert hooks.span(seconds) == (f"{hours}h {rest // 60}m" if hours else f"{rest // 60}m")


@pytest.fixture
def cache(tmp_path, monkeypatch):
    path = tmp_path / "git" / "usage.json"
    monkeypatch.setattr(hooks, "USAGE_CACHE", path)
    return path


def fake_budget(monkeypatch, out):
    budget = hooks.ROOT / "tasks" / "claude" / "budget.py"
    budget.parent.mkdir(parents=True, exist_ok=True)
    budget.touch()
    calls = []

    def run(*args, **kwargs):
        calls.append(args[0])
        return completed(0, out)

    monkeypatch.setattr(hooks.subprocess, "run", run)
    return calls


def test_usage_reading_uses_fresh_cache(cache, monkeypatch):
    cache.parent.mkdir()
    reading = {"read_at": time.time(), "reading": {"ok": True, "n": 1}}
    cache.write_text(json.dumps(reading), encoding="utf-8")
    monkeypatch.setattr(hooks.subprocess, "run", lambda *a, **k: pytest.fail("spawned"))
    assert hooks.usage_reading() == {"ok": True, "n": 1}


def test_usage_reading_refreshes_stale_cache(cache, monkeypatch):
    cache.parent.mkdir()
    cache.write_text(json.dumps({"read_at": 0, "reading": {"old": True}}), encoding="utf-8")
    calls = fake_budget(monkeypatch, json.dumps({"ok": True, "over_ceiling": False}))
    assert hooks.usage_reading() == {"ok": True, "over_ceiling": False}
    assert len(calls) == 1
    assert json.loads(cache.read_text(encoding="utf-8"))["reading"]["ok"] is True


def test_usage_reading_ignores_corrupt_cache(cache, monkeypatch):
    cache.parent.mkdir()
    cache.write_text("not json", encoding="utf-8")
    fake_budget(monkeypatch, json.dumps({"ok": True}))
    assert hooks.usage_reading() == {"ok": True}


def test_usage_reading_non_json_is_empty(cache, monkeypatch):
    fake_budget(monkeypatch, "garbage")
    assert hooks.usage_reading() == {}
    assert not cache.exists()


def test_usage_reading_not_ok_is_empty(cache, monkeypatch):
    fake_budget(monkeypatch, json.dumps({"ok": False}))
    assert hooks.usage_reading() == {}
    assert not cache.exists()


def test_usage_reading_survives_cache_write_failure(cache, monkeypatch):
    fake_budget(monkeypatch, json.dumps({"ok": True}))

    def boom(*args, **kwargs):
        raise OSError("read-only")

    monkeypatch.setattr(hooks.Path, "write_text", boom)
    assert hooks.usage_reading() == {"ok": True}


def test_usage_reading_without_a_budget_script_is_empty(cache, monkeypatch):
    monkeypatch.setattr(hooks, "budget_script", lambda: None)
    monkeypatch.setattr(hooks.subprocess, "run", lambda *a, **k: pytest.fail("spawned"))
    assert hooks.usage_reading() == {}


def test_run_resolves_the_executable_without_a_shell(monkeypatch):
    seen = {}

    def run(*args, **kwargs):
        seen["args"], seen["kwargs"] = args, kwargs
        return completed(0)

    monkeypatch.setattr(hooks.shutil, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(hooks.subprocess, "run", run)
    hooks.run("task", "py:check")
    assert seen["args"] == (["/bin/task", "py:check"],)
    assert seen["kwargs"]["shell"] is False
    assert seen["kwargs"]["cwd"] == hooks.ROOT


def test_pre_tool_use_allows_agent_under_ceiling(monkeypatch, capsys):
    monkeypatch.setattr(hooks, "usage_reading", lambda: {"over_ceiling": False})
    assert hooks.pre_tool_use(AGENT) == 0
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("kind", [None, "", "general-purpose", "claude", "fork"])
def test_pre_tool_use_denies_generic_agents(monkeypatch, capsys, kind):
    monkeypatch.setattr(hooks, "usage_reading", lambda: pytest.fail("read usage"))
    event = {"tool_name": "Agent", "tool_input": {"subagent_type": kind, "model": "sonnet"}}
    assert hooks.pre_tool_use(event) == 0
    result = decision(capsys)
    assert result["permissionDecision"] == "deny"
    assert "generic" in result["permissionDecisionReason"]


def session(tmp_path, metas):
    folder = tmp_path / "s1" / "subagents"
    folder.mkdir(parents=True)
    for number, text in enumerate(metas):
        (folder / f"agent-{number}.meta.json").write_text(text, encoding="utf-8")
    return str(tmp_path / "s1.jsonl")


def test_running_agents_counts_unfinished_fresh_metas(tmp_path):
    metas = ['{"finished": true}', '{"agentType": "x"}', "nope", "[]", "{}"]
    transcript = session(tmp_path, metas)
    assert hooks.running_agents(transcript, time.time()) == 2
    assert hooks.running_agents(transcript, time.time() + hooks.RUNNING_SECONDS) == 0
    assert hooks.running_agents("", time.time()) == 0


def test_pre_tool_use_denies_past_the_agent_limit(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(hooks, "usage_reading", dict)
    transcript = session(tmp_path, ["{}"] * hooks.MAX_AGENTS)
    hooks.pre_tool_use({**AGENT, "transcript_path": transcript})
    assert "limit is 6" in decision(capsys)["permissionDecisionReason"]


def test_stop_reports_ceiling_after_gates_pass(gates, monkeypatch, capsys):
    gates[1].marker.touch()
    monkeypatch.setattr(hooks, "run", lambda *a: completed(0))
    reading = {"over_ceiling": True, "wait_seconds": 600}
    monkeypatch.setattr(hooks, "usage_reading", lambda: reading)
    assert hooks.stop({}) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "task claude:resume" in captured.err
    assert "10m" in captured.err


def test_failure_falls_back_to_the_last_lines():
    total = hooks.TAIL_LINES + 20
    result = completed(1, "\n".join(f"line {i}" for i in range(total)))
    reason = hooks.failure("py:check", result, (".py:",))
    assert "line 19" not in reason
    assert "line 20" in reason
    assert f"line {total - 1}" in reason


def run_main(monkeypatch, argv, stdin):
    monkeypatch.setattr(sys, "stdin", io.StringIO(stdin))
    return hooks.main(argv)


@pytest.mark.parametrize(
    ("name", "target"),
    [
        ("post-tool-use", "post_tool_use"),
        ("pre-tool-use", "pre_tool_use"),
        ("pre-bash", "pre_bash"),
        ("subagent-start", "subagent_start"),
        ("subagent-stop", "subagent_stop"),
        ("stop", "stop"),
    ],
)
def test_main_dispatches_each_event(monkeypatch, name, target):
    seen = []
    monkeypatch.setattr(hooks, target, lambda event: seen.append(event) or 7)
    assert run_main(monkeypatch, [name], '{"a": 1}') == 7
    assert seen == [{"a": 1}]


def test_main_reads_sys_argv_by_default(monkeypatch):
    seen = []
    monkeypatch.setattr(hooks, "stop", lambda event: seen.append(event) or 0)
    monkeypatch.setattr(sys, "argv", ["hooks.py", "stop"])
    assert run_main(monkeypatch, None, '{"a": 1}') == 0
    assert seen == [{"a": 1}]


@pytest.mark.parametrize("argv", [["bogus"], []])
def test_main_rejects_unknown_event(monkeypatch, capsys, argv):
    assert run_main(monkeypatch, argv, "{}") == 2
    assert "usage" in capsys.readouterr().err


@pytest.mark.parametrize("text", ["{nope", "", "[1, 2]", '"x"'])
def test_payload_invalid_json_is_empty(monkeypatch, text):
    monkeypatch.setattr(sys, "stdin", io.StringIO(text))
    assert hooks.payload() == {}


# ---- Agent policy: model rule, tool names, ledger --------------------------------------


def test_pre_tool_use_refuses_an_agent_without_a_cheap_model(monkeypatch, capsys):
    monkeypatch.setattr(hooks, "usage_reading", lambda: pytest.fail("read usage"))
    hooks.pre_tool_use(agent("unknown-agent", model=None))
    assert "would run on" in decision(capsys)["permissionDecisionReason"]


def test_pre_tool_use_refuses_opus(capsys):
    hooks.pre_tool_use(agent("toolsmith", model="opus"))
    assert "'opus'" in decision(capsys)["permissionDecisionReason"]


def test_pre_tool_use_accepts_a_model_from_the_project_definition(monkeypatch, capsys):
    monkeypatch.setattr(hooks, "usage_reading", dict)
    folder = hooks.ROOT / ".claude" / "agents"
    folder.mkdir(parents=True)
    (folder / "indexer.md").write_text("---\nname: indexer\nmodel: haiku\n---\n", encoding="utf-8")
    assert hooks.pre_tool_use(agent("indexer", model=None)) == 0
    assert capsys.readouterr().out == ""


def test_defined_model_reads_a_plugin_agent_by_its_short_name():
    folder = hooks.PLUGIN_AGENTS
    folder.mkdir(parents=True)
    (folder / "toolsmith.md").write_text("---\nmodel: sonnet\n---\n", encoding="utf-8")
    assert hooks.defined_model("some-plugin:toolsmith") == "sonnet"
    assert hooks.defined_model("../toolsmith") == ""


def test_pre_tool_use_polices_the_task_tool_name(capsys):
    hooks.pre_tool_use({"tool_name": "Task", "tool_input": {"subagent_type": "general-purpose"}})
    assert decision(capsys)["permissionDecision"] == "deny"


def test_pre_tool_use_reserves_a_lane(monkeypatch):
    monkeypatch.setattr(hooks, "usage_reading", dict)
    hooks.pre_tool_use({**AGENT, "tool_use_id": "t1"})
    assert list(json.loads(hooks.LEDGER.read_text(encoding="utf-8"))["pending"]) == ["t1"]


def test_pre_tool_use_refuses_when_the_ledger_is_full(monkeypatch, capsys):
    monkeypatch.setattr(hooks, "usage_reading", dict)
    now = time.time()
    pending = {f"t{n}": now for n in range(hooks.MAX_AGENTS)}
    hooks.LEDGER.write_text(json.dumps({"running": {}, "pending": pending}), encoding="utf-8")
    hooks.pre_tool_use(AGENT)
    assert "already running" in decision(capsys)["permissionDecisionReason"]


def test_ledger_forgets_expired_entries():
    old = time.time() - hooks.RUNNING_SECONDS - 1
    state = {"running": {"a": old}, "pending": {"t": old}}
    hooks.LEDGER.write_text(json.dumps(state), encoding="utf-8")
    assert hooks.load_ledger(time.time()) == {"running": {}, "pending": {}}


def test_ledger_survives_a_corrupt_file():
    hooks.LEDGER.write_text("[]", encoding="utf-8")
    assert hooks.load_ledger(time.time()) == {"running": {}, "pending": {}}


# ---- Git guard -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "git checkout -- a.py",
        "git switch main",
        "git restore a.py",
        "git restore --staged --worktree a.py",
        "git -C sub reset --hard",
        "git clean -fd",
        "git stash",
        "git add -A",
        "git add .",
        "git commit -am x",
        "rtk git checkout .",
        "FOO=1 git stash pop",
        "bash -c 'git clean -fd'",
        "echo ok && git checkout .",
    ],
)
def test_git_refusal_denies_discards(command):
    assert "Refused" in hooks.git_refusal(command, tracked=lambda path, cwd: False)


@pytest.mark.parametrize(
    "command",
    [
        "git status",
        "git diff",
        "git restore --staged a.py",
        "git add a.py",
        "git commit -m x -- a.py",
        "rm build/out.txt",
    ],
)
def test_git_refusal_allows_safe_commands(command):
    assert hooks.git_refusal(command, tracked=lambda path, cwd: True) == ""


def test_git_refusal_denies_rm_of_a_tracked_file(monkeypatch, tmp_path):
    monkeypatch.setattr(hooks.tempfile, "gettempdir", lambda: str(tmp_path / "elsewhere"))
    assert hooks.git_refusal("rm src/a.py", tracked=lambda path, cwd: path == "src/a.py")
    assert hooks.git_refusal("rm src/b.py", tracked=lambda path, cwd: path == "src/a.py") == ""


# ---- CLI per subcommand: allow, deny, malformed stdin ----------------------------------


def call(monkeypatch, argv, event):
    return run_main(monkeypatch, argv, json.dumps(event))


def ledger():
    return json.loads(hooks.LEDGER.read_text(encoding="utf-8"))


def test_cli_post_tool_use_allow(monkeypatch, capsys):
    assert call(monkeypatch, ["post-tool-use"], {"tool_input": {"file_path": "a.png"}}) == 0
    assert capsys.readouterr().out == ""
    assert not hooks.GATES[0].marker.exists()


def test_cli_post_tool_use_deny(monkeypatch, capsys):
    assert call(monkeypatch, ["post-tool-use"], {"tool_input": {"file_path": "src/a.py"}}) == 0
    assert capsys.readouterr().out == ""
    assert hooks.GATES[0].marker.exists()


def test_cli_pre_tool_use_allow(monkeypatch, capsys):
    monkeypatch.setattr(hooks, "usage_reading", dict)
    assert call(monkeypatch, ["pre-tool-use"], AGENT) == 0
    assert capsys.readouterr().out == ""
    assert len(ledger()["pending"]) == 1


def test_cli_pre_tool_use_deny(monkeypatch, capsys):
    assert call(monkeypatch, ["pre-tool-use"], agent("general-purpose")) == 0
    assert decision(capsys)["permissionDecision"] == "deny"


def test_cli_pre_bash_allow(monkeypatch, capsys):
    bash = {"tool_name": "Bash", "tool_input": {"command": "git checkout ."}}
    assert call(monkeypatch, ["pre-bash"], bash) == 0
    assert call(monkeypatch, ["pre-bash"], {**bash, "agent_id": "a1", "tool_input": {}}) == 0
    assert capsys.readouterr().out == ""


def test_cli_pre_bash_deny(monkeypatch, capsys):
    event = {
        "tool_name": "Bash",
        "agent_id": "a1",
        "tool_input": {"command": "git checkout -- a.py"},
    }
    assert call(monkeypatch, ["pre-bash"], event) == 0
    result = decision(capsys)
    assert result["permissionDecision"] == "deny"
    assert "git checkout -- a.py" in result["permissionDecisionReason"]


def fill_lanes(monkeypatch):
    for n in range(hooks.MAX_AGENTS):
        call(monkeypatch, ["subagent-start"], {"agent_id": f"a{n}"})


def test_cli_subagent_start_allow(monkeypatch, capsys):
    monkeypatch.setattr(hooks, "usage_reading", dict)
    call(monkeypatch, ["pre-tool-use"], {**AGENT, "tool_use_id": "t1"})
    assert call(monkeypatch, ["subagent-start"], {"agent_id": "a1"}) == 0
    assert capsys.readouterr().out == ""
    assert list(ledger()["running"]) == ["a1"]
    assert ledger()["pending"] == {}


def test_cli_subagent_start_deny(monkeypatch, capsys):
    monkeypatch.setattr(hooks, "usage_reading", dict)
    fill_lanes(monkeypatch)
    call(monkeypatch, ["pre-tool-use"], AGENT)
    assert "already running" in decision(capsys)["permissionDecisionReason"]


def test_cli_subagent_stop_allow(monkeypatch, capsys):
    monkeypatch.setattr(hooks, "usage_reading", dict)
    fill_lanes(monkeypatch)
    assert call(monkeypatch, ["subagent-stop"], {"agent_id": "a0"}) == 0
    call(monkeypatch, ["pre-tool-use"], AGENT)
    assert capsys.readouterr().out == ""


def test_cli_subagent_stop_deny(monkeypatch, capsys):
    monkeypatch.setattr(hooks, "usage_reading", dict)
    fill_lanes(monkeypatch)
    assert call(monkeypatch, ["subagent-stop"], {"agent_id": "someone-else"}) == 0
    call(monkeypatch, ["pre-tool-use"], AGENT)
    assert decision(capsys)["permissionDecision"] == "deny"


def test_cli_stop_allow(monkeypatch, capsys):
    hooks.GATES[0].marker.touch()
    calls = fake(monkeypatch, 0, "")
    assert call(monkeypatch, ["stop"], {"session_id": "s"}) == 0
    assert capsys.readouterr().out == ""
    assert calls[0] == ("task", "validate")
    assert not hooks.GATES[0].marker.exists()


def test_cli_stop_deny(monkeypatch, capsys):
    hooks.GATES[0].marker.touch()
    calls = fake(monkeypatch, 1, "src/a.py:1:1: F401 unused")
    assert call(monkeypatch, ["stop", "--task", "check"], {"session_id": "s"}) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["decision"] == "block"
    assert calls == [("task", "check")]
    assert hooks.GATES[0].marker.exists()


@pytest.mark.parametrize(
    "event",
    ["post-tool-use", "pre-tool-use", "pre-bash", "subagent-start", "subagent-stop", "stop"],
)
@pytest.mark.parametrize("stdin", ["{nope", "", "[1, 2]"])
def test_cli_malformed_stdin_fails_open(monkeypatch, capsys, event, stdin):
    hooks.GATES[0].marker.touch()
    monkeypatch.setattr(hooks, "run", lambda *a: pytest.fail("ran"))
    monkeypatch.setattr(hooks, "usage_reading", lambda: pytest.fail("read usage"))
    assert run_main(monkeypatch, [event], stdin) == 0
    assert capsys.readouterr().out == ""
    assert hooks.GATES[0].marker.exists()
    assert not hooks.LEDGER.exists()


def test_cli_internal_error_fails_open(monkeypatch, capsys):
    def boom(event):
        raise RuntimeError("bug")

    monkeypatch.setattr(hooks, "pre_tool_use", boom)
    assert call(monkeypatch, ["pre-tool-use"], AGENT) == 0
    assert capsys.readouterr().out == ""


# ---- Hardening from the security review -----------------------------------------------


def untracked(_path, _root):
    return False


def test_unparseable_segment_fails_closed(tmp_path):
    assert hooks.inner_refusal('git checkout "x', tmp_path, untracked)


@pytest.mark.parametrize("flags", ["-c", "-lc", "-ec", "-xc"])
def test_shell_flag_clusters_with_c_are_inspected(tmp_path, flags):
    assert hooks.inner_refusal(f"bash {flags} 'git checkout .'", tmp_path, untracked)


@pytest.mark.parametrize(
    ("command", "refused"),
    [
        ("git rm notes.txt", True),
        ("git rm --cached notes.txt", False),
        ("git checkout-index -a -f", True),
        ("git reset --keep HEAD~1", True),
        ("git read-tree -u HEAD", True),
        ("git status", False),
    ],
)
def test_git_deny_table_covers_destructive_plumbing(tmp_path, command, refused):
    assert bool(hooks.inner_refusal(command, tmp_path, untracked)) is refused


def test_future_dated_usage_cache_is_ignored(tmp_path, monkeypatch):
    cache = tmp_path / "usage.json"
    reading = {"ok": True, "over_ceiling": True}
    cache.write_text(
        json.dumps({"read_at": time.time() + 10_000, "reading": reading}), encoding="utf-8"
    )
    monkeypatch.setattr(hooks, "USAGE_CACHE", cache)
    monkeypatch.setattr(hooks, "budget_script", lambda: None)
    assert hooks.usage_reading() == {}


# ---- Final review fixes ----------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        'grep -E "a|b" notes.txt',
        'python -c "a = 1; b = 2"',
        "bash -c 'echo x; echo y'",
        "git commit -m \"$(cat <<'EOF'\nsubject; detail\n\nbody | more\nEOF\n)\" -- a.py",
    ],
)
def test_quoted_separators_do_not_split_commands(tmp_path, command):
    assert hooks.inner_refusal(command, tmp_path, untracked) == ""


def test_unquoted_separator_still_splits(tmp_path):
    assert hooks.inner_refusal('echo "x"; git checkout .', tmp_path, untracked)


@pytest.mark.parametrize(
    "output",
    ['task: Task "validate" does not exist', "task: No Taskfile found at /repo"],
)
def test_missing_task_or_taskfile_is_did_not_run(output):
    assert hooks.skip_reason(output) is not None


def test_state_dir_follows_gitfile_worktrees(tmp_path):
    real = tmp_path / "real-git-dir"
    real.mkdir()
    checkout = tmp_path / "wt"
    checkout.mkdir()
    (checkout / ".git").write_text(f"gitdir: {real}\n", encoding="utf-8")
    assert hooks.state_dir(checkout) == real


def test_state_dir_plain_repo_and_no_repo(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    assert hooks.state_dir(repo) == repo / ".git"
    bare = tmp_path / "plain"
    bare.mkdir()
    fallback = hooks.state_dir(bare)
    assert not fallback.is_relative_to(bare)


@pytest.mark.no_opt_in
def test_post_tool_use_writes_nothing_without_opt_in(tmp_path, monkeypatch):
    monkeypatch.setattr(hooks, "ROOT", tmp_path)
    marker = tmp_path / "state" / "dirty"
    gate = hooks.GATES[0]._replace(marker=marker)
    monkeypatch.setattr(hooks, "GATES", (gate,))
    event = {"tool_input": {"file_path": str(tmp_path / "a.py")}}
    assert hooks.post_tool_use(event) == 0
    assert not marker.exists()


def test_state_fallback_is_per_user_not_shared_temp(tmp_path, monkeypatch):
    import tempfile
    from pathlib import Path

    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    bare = tmp_path / "plain"
    bare.mkdir()
    fallback = hooks.state_dir(bare)
    assert fallback.is_relative_to(tmp_path / "state")
    assert not fallback.is_relative_to(Path(tempfile.gettempdir()) / "crepidoma")


# ---- Model policy: Opus main thread, Sonnet subagents, Haiku for reads -----------------


@pytest.mark.parametrize("model", ["sonnet", "haiku", "claude-sonnet-5-5", "claude-haiku-5-5"])
def test_subagent_models_allowed(model):
    assert hooks.agent_refusal({"subagent_type": "toolsmith", "model": model}) is None


@pytest.mark.parametrize("model", ["opus", "claude-opus-5-5", "fable", "inherit"])
def test_subagent_heavy_models_refused(model):
    assert hooks.agent_refusal({"subagent_type": "toolsmith", "model": model})


@pytest.mark.parametrize(("env", "refused"), [("sonnet", False), ("haiku", False), ("opus", True)])
def test_subagent_model_env_must_be_sonnet_or_haiku(monkeypatch, env, refused):
    monkeypatch.setenv("CLAUDE_CODE_SUBAGENT_MODEL", env)
    result = hooks.agent_refusal({"subagent_type": "toolsmith", "model": "sonnet"})
    assert bool(result) is refused


def test_budget_script_is_the_plugin_copy():
    script = hooks.budget_script()
    assert script is not None
    assert script.name == "budget.py"
    assert script.parent == Path(hooks.__file__).resolve().parent


@pytest.mark.parametrize(
    ("command", "refused"),
    [
        ("task git:commit -- 'msg'", True),
        ("task git:status", False),
        ("task repo:outline x", False),
    ],
)
def test_subagents_cannot_publish_through_git_commit_task(tmp_path, command, refused):
    assert bool(hooks.inner_refusal(command, tmp_path, untracked)) is refused
