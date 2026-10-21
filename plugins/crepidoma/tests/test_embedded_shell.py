import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "lint" / "embedded_shell.py"
spec = importlib.util.spec_from_file_location("embedded_shell", SCRIPT)
assert spec
assert spec.loader
shell = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shell)

TASKFILE = """version: "3"
tasks:
  hello:
    cmds:
      - |
        echo one

        echo two

      - echo inline
"""


def test_blocks_carry_task_line_and_dedented_body(tmp_path):
    path = tmp_path / "Taskfile.yml"
    path.write_text(TASKFILE, encoding="utf-8")
    assert shell.blocks(path) == [("hello", 6, "echo one\n\necho two")]


def test_templating_becomes_a_shell_word():
    assert shell.TEMPLATE.sub("TASKVAR", 'cp {{.SRC}} "{{.HOME}}/x"') == 'cp TASKVAR "TASKVAR/x"'


def test_vendored_marketplace_is_skipped():
    assert ".claude/marketplace/" in shell.SKIP
