from pathlib import Path

import ratchet


def write(path: Path, lines: int) -> None:
    path.write_text("x\n" * lines, encoding="utf-8")


def test_new_long_file_fails(tmp_path: Path, capsys):
    big = tmp_path / "big.py"
    write(big, 5)
    assert ratchet.long_files([str(big)], tmp_path / "b", max_lines=3, update=False) == 1
    assert "new long file" in capsys.readouterr().out


def test_baselined_file_may_shrink_not_grow(tmp_path: Path):
    big = tmp_path / "big.py"
    base = tmp_path / "long.baseline"
    write(big, 5)
    assert ratchet.long_files([str(big)], base, 3, update=True) == 0
    write(big, 4)
    assert ratchet.long_files([str(big)], base, 3, update=False) == 0
    write(big, 6)
    assert ratchet.long_files([str(big)], base, 3, update=False) == 1


def test_short_and_missing_files_ignored(tmp_path: Path):
    small = tmp_path / "s.py"
    write(small, 2)
    files = [str(small), str(tmp_path / "gone.py")]
    assert ratchet.long_files(files, tmp_path / "b", 3, update=False) == 0


def test_metric_up(tmp_path: Path):
    base = tmp_path / "coverage.baseline"
    assert ratchet.metric(base, 80.0, "up", update=False) == 0
    assert base.read_text(encoding="utf-8").strip() == "80.0"
    assert ratchet.metric(base, 79.9, "up", update=False) == 1
    assert ratchet.metric(base, 81.0, "up", update=True) == 0
    assert base.read_text(encoding="utf-8").strip() == "81.0"


def test_metric_down(tmp_path: Path):
    base = tmp_path / "duplication.baseline"
    base.write_text("5\n", encoding="utf-8")
    assert ratchet.metric(base, 6.0, "down", update=False) == 1
    assert ratchet.metric(base, 4.0, "down", update=False) == 0


def test_baselines_are_written_with_lf(tmp_path: Path):
    big = tmp_path / "big.py"
    write(big, 5)
    base = tmp_path / "long.baseline"
    ratchet.long_files([str(big)], base, 3, update=True)
    assert b"\r\n" not in base.read_bytes()
    value = tmp_path / "coverage.baseline"
    ratchet.metric(value, 80.0, "up", update=False)
    assert b"\r\n" not in value.read_bytes()


def test_main_long_files(tmp_path: Path):
    big = tmp_path / "big.py"
    write(big, 5)
    args = ["long-files", "--baseline", str(tmp_path / "b"), "--max-lines", "3", str(big)]
    assert ratchet.main(args) == 1
