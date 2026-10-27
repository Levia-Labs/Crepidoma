import io
import sys
from pathlib import Path

import digest


def test_output_is_bounded():
    out = digest.digest("line\n" * 500, grep=r"^never$", tail=12, max_bytes=1024)
    assert len(out.splitlines()) <= digest.MAX_LINES + 1
    assert len(out.encode("utf-8")) <= 1024


def test_main_survives_narrow_console_encoding(tmp_path: Path, monkeypatch):
    target = tmp_path / "u.txt"
    target.write_text("info " + chr(0x2139) + " sign\n", encoding="utf-8")
    raw = io.BytesIO()
    monkeypatch.setattr("sys.stdout", io.TextIOWrapper(raw, encoding="cp1250"))
    assert digest.main([str(target)]) == 0
    sys.stdout.flush()
    assert b"info" in raw.getvalue()


def test_main_reads_file(tmp_path: Path, capsys):
    target = tmp_path / "a.txt"
    target.write_text("one\ntwo\n", encoding="utf-8")
    assert digest.main([str(target)]) == 0
    assert capsys.readouterr().out.startswith("lines 2")


def run(tmp_path: Path, name: str, text: str, capsys) -> list[str]:
    target = tmp_path / name
    target.write_text(text, encoding="utf-8")
    assert digest.main([str(target), "--max-bytes", "4000"]) == 0
    return capsys.readouterr().out.splitlines()


def test_markdown_lists_headings_outside_fences(tmp_path: Path, capsys):
    out = run(tmp_path, "a.md", "# One\ntext\n```\n# not a heading\n```\n## Two\n", capsys)
    assert out[0].startswith("lines 6 bytes")
    assert out[1:] == ["1: # One", "6: ## Two"]


def test_code_lists_top_level_definitions_with_line_numbers(tmp_path: Path, capsys):
    out = run(
        tmp_path,
        "a.py",
        "import os\n\ndef f():\n    def inner(): pass\n\nclass C:\n    pass\n",
        capsys,
    )
    assert out[1:] == ["3: def f():", "6: class C:"]


def test_log_lists_failure_lines(tmp_path: Path, capsys):
    text = "ok\nFAIL a\nfine\nERROR b\npanic: c\nTraceback (most recent)\n"
    out = run(tmp_path, "a.log", text, capsys)
    assert [x.split(": ", 1)[0] for x in out[1:]] == ["2", "4", "5", "6"]


def test_other_text_shows_first_and_last_five(tmp_path: Path, capsys):
    out = run(tmp_path, "a.txt", "".join(f"l{n}\n" for n in range(1, 31)), capsys)
    assert out[1:] == ["l1", "l2", "l3", "l4", "l5", "...", "l26", "l27", "l28", "l29", "l30"]


def test_output_never_exceeds_20_lines(tmp_path: Path, capsys):
    out = run(tmp_path, "a.go", "".join(f"func f{n}() {{}}\n" for n in range(100)), capsys)
    assert len(out) <= digest.MAX_LINES


def test_stdin_input(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(b"a\nb\n")))
    assert digest.main([]) == 0
    assert capsys.readouterr().out.splitlines() == ["lines 2 bytes 4", "a", "b"]
