import json

import history
import pytest


def write_transcript(folder, commands, name="s1.jsonl"):
    folder.mkdir(parents=True, exist_ok=True)
    lines = []
    for command in commands:
        block = {"type": "tool_use", "name": "Bash", "input": {"command": command}}
        lines.append(json.dumps({"message": {"content": [block]}}))
    (folder / name).write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.mark.parametrize("prefix", ["rtk ", "rtk proxy "])
def test_normalise_strips_rtk_prefix(prefix):
    assert history.normalise(f"{prefix}git status") == history.normalise("git status")


def test_normalise_keeps_rtk_inside_command():
    assert history.normalise("echo rtk git") == "echo rtk git"


def test_normalise_collapses_quoted_variadic_values():
    a = history.normalise('task fmt FILES="a.py b.py c.py"')
    b = history.normalise('task fmt FILES="x.py y.py"')
    assert a == b == "task fmt FILES=<paths>"


def test_normalise_keeps_single_word_quoted_value():
    assert history.normalise('task x NAME="one"') == 'task x NAME="one"'


def test_commands_merge_after_normalising(tmp_path, capsys):
    write_transcript(tmp_path, ["rtk git status", "git status", "rtk proxy git status"])
    assert history.main(["commands", "--dir", str(tmp_path), "--min", "3"]) == 0
    assert capsys.readouterr().out.strip() == "3  git status"


def test_prompts_accepts_dir_and_ignores_it(tmp_path, capsys):
    log = tmp_path / "h.jsonl"
    log.write_text(
        "\n".join(json.dumps({"display": "please fix the build"}) for _ in range(2)) + "\n",
        encoding="utf-8",
    )
    argv = ["prompts", "--dir", str(tmp_path / "missing"), "--prompts", str(log)]
    assert history.main(argv) == 0
    assert "please fix the build" in capsys.readouterr().out
