import json
import re
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
QUOTED_SCRIPT = re.compile(r'"\$\{CLAUDE_PLUGIN_ROOT\}/([^"]+)"')


def load():
    return json.loads((PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8"))


def commands():
    for groups in load()["hooks"].values():
        for group in groups:
            for hook in group["hooks"]:
                yield hook["command"]


def test_commands_quote_plugin_root_and_scripts_exist():
    found = list(commands())
    assert found
    for command in found:
        match = QUOTED_SCRIPT.search(command)
        assert match, command
        assert (PLUGIN / match.group(1)).is_file(), command


def test_expected_events():
    assert {"SessionStart", "PreToolUse"} <= set(load()["hooks"])


def test_every_hooks_py_subcommand_is_wired():
    wired = " ".join(commands())
    for subcommand in (
        "pre-bash",
        "pre-edit",
        "post-edit",
        "pre-tool-use",
        "post-tool-use",
        "subagent-start",
        "subagent-stop",
        "stop",
    ):
        assert f'hooks.py" {subcommand}' in wired, subcommand
