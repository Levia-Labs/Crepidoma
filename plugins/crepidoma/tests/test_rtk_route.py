import io
import json
import random
import re
import shutil
import subprocess
import sys

import pytest
import rtk_route as route

FILTERS = r"""
schema_version = 1
[filters.gate]
match_command = "^task\\s+(validate|boom)\\b"
strip_lines_matching = ["^noise$"]
[filters.grep]
match_command = "^e?grep\\b"
[filters.other]
description = "no match_command"
"""


@pytest.fixture
def root(tmp_path, monkeypatch):
    (tmp_path / ".rtk").mkdir()
    (tmp_path / ".rtk" / "filters.toml").write_text(FILTERS, encoding="utf-8")
    monkeypatch.setattr(shutil, "which", lambda name: "/bin/rtk" if name == "rtk" else None)
    return tmp_path


def event(command, **extra):
    return {"tool_name": "Bash", "tool_input": {"command": command, "timeout": 5}, **extra}


@pytest.mark.parametrize("agent", [None, "a1"])
def test_rewrites_a_matching_command(root, agent):
    extra = {"agent_id": agent} if agent else {}
    out = route.rewrite(event("task validate", **extra), root)
    updated = out["hookSpecificOutput"]["updatedInput"]
    assert updated == {"command": "rtk task validate", "timeout": 5}
    assert out["hookSpecificOutput"]["hookEventName"] == "PreToolUse"


@pytest.mark.parametrize(
    "command",
    [
        "task validate | tail",
        "task validate && echo x",
        "task validate; ls",
        "task validate > out.txt",
        "task validate 2>&1",
        "(task validate)",
        "task validate $(echo)",
        "task validate `x`",
        "rtk task validate",
        "task lint",
        "",
    ],
)
def test_leaves_other_commands_alone(root, command):
    assert route.rewrite(event(command), root) is None


def test_no_rtk_means_no_rewrite(root, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    assert route.rewrite(event("task validate"), root) is None


@pytest.mark.parametrize("content", [None, "not = [toml", "[filters.x]\nmatch_command = '('"])
def test_missing_or_bad_filters_do_nothing(tmp_path, monkeypatch, content):
    monkeypatch.setattr(shutil, "which", lambda name: "/bin/rtk")
    if content is not None:
        (tmp_path / ".rtk").mkdir()
        (tmp_path / ".rtk" / "filters.toml").write_text(content, encoding="utf-8")
    assert route.rewrite(event("task validate"), tmp_path) is None


def test_wrap(root):
    assert route.wrap(("task", "validate"), root) == ("rtk", "task", "validate")
    assert route.wrap(("task", "lint"), root) == ("task", "lint")


def test_main_prints_json_and_fails_open(root, monkeypatch, capsys):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(root))
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(event("task boom"))))
    assert route.main() == 0
    assert json.loads(capsys.readouterr().out)["hookSpecificOutput"]["updatedInput"]
    monkeypatch.setattr(sys, "stdin", io.StringIO("{bad"))
    assert route.main() == 0
    assert capsys.readouterr().out == ""


def test_property_never_rewrites_compound_or_prefixed(tmp_path, monkeypatch):
    # The filter pattern matches anything, so only the structural guards can refuse.
    (tmp_path / ".rtk").mkdir()
    (tmp_path / ".rtk" / "filters.toml").write_text(
        '[filters.a]\nmatch_command = "."\n', encoding="utf-8"
    )
    monkeypatch.setattr(shutil, "which", lambda name: "/bin/rtk")
    rng = random.Random(7)  # noqa: S311 - a fixed seed, not cryptography
    alphabet = "ab rtk|&;<>()`$\n{}-"
    for _ in range(500):
        text = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 12)))
        out = route.rewrite(event(text), tmp_path)
        if out is not None:
            assert not route.COMPOUND.search(text.strip())
            assert not re.match(r"rtk(\s|$)", text.strip())


@pytest.mark.skipif(
    shutil.which("rtk") is None or shutil.which("task") is None, reason="needs rtk and task"
)
def test_exit_code_survives_rtk(tmp_path):
    (tmp_path / "Taskfile.yml").write_text(
        'version: "3"\ntasks:\n  boom:\n    cmds:\n      - echo noise\n      - exit 3\n',
        encoding="utf-8",
    )
    (tmp_path / ".rtk").mkdir()
    (tmp_path / ".rtk" / "filters.toml").write_text(FILTERS, encoding="utf-8")
    run = subprocess.run(["rtk", "task", "boom"], cwd=tmp_path, capture_output=True, text=True)
    assert run.returncode != 0


def test_noise_matches_passed_rows_and_not_failures():
    assert route.NOISE.match("ruff.........................................Passed")
    assert route.NOISE.match("prettier.....(unchanged)\x1b[0m")
    assert route.NOISE.match("hook.......\x1b[32mPassed\x1b[m")
    assert not route.NOISE.match("ruff..............................Failed")
    assert not route.NOISE.match("- hook id: ruff")


@pytest.mark.parametrize(
    "command",
    [
        "grep -q foo file",
        "grep -qE foo file",
        "grep -Eq foo file",
        "grep -iqx foo file",
        "grep --quiet foo file",
        "grep --silent foo file",
        "egrep -q foo file",
        "grep foo file -q",
    ],
)
def test_grep_quiet_stays_out_of_rtk(root, command):
    assert route.rewrite(event(command), root) is None


@pytest.mark.parametrize("command", ["grep foo file", "grep -rn foo .", "grep -e quiet file"])
def test_other_grep_still_routes(root, command):
    assert route.rewrite(event(command), root) is not None
