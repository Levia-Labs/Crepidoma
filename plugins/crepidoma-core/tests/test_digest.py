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
    target.write_text("info ℹ sign\n", encoding="utf-8")
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
