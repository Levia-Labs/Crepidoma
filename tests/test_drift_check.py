from pathlib import Path

import drift_check


def make(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def test_states_with_crlf_normalised(tmp_path: Path):
    root, pillar = tmp_path / "crep", tmp_path / "pillar"
    make(root / "a/same.py", b"one\n")
    make(pillar / "x/same.py", b"one\r\n")
    make(root / "a/diff.py", b"one\n")
    make(pillar / "x/diff.py", b"two\n")
    make(root / "a/gone.py", b"one\n")
    entries = [
        {"crepidoma": "a/same.py", "pillar": ["y/same.py", "x/same.py"]},
        {"crepidoma": "a/diff.py", "pillar": ["x/diff.py"]},
        {"crepidoma": "a/gone.py", "pillar": ["x/gone.py"]},
    ]
    assert drift_check.check(pillar, entries, root) == [
        ("duplicate", "a/same.py", "x/same.py"),
        ("drifted", "a/diff.py", "x/diff.py"),
        ("absent", "a/gone.py", "-"),
    ]


def test_main_rejects_missing_pillar(tmp_path: Path):
    assert drift_check.main([str(tmp_path / "nope")]) == 2


def test_main_exit_and_report(tmp_path: Path, capsys):
    root, pillar = tmp_path / "crep", tmp_path / "pillar"
    make(root / "a/f.py", b"one\n")
    make(pillar / "a/f.py", b"two\n")
    mapping = tmp_path / "map.toml"
    mapping.write_text('[[file]]\ncrepidoma = "a/f.py"\npillar = ["a/f.py"]\n', encoding="utf-8")
    report = tmp_path / "report.tsv"
    args = [str(pillar), "--map", str(mapping), "--root", str(root), "--report", str(report)]
    assert drift_check.main(args) == 1
    assert "drifted" in report.read_text(encoding="utf-8")
    assert "drifted=1" in capsys.readouterr().out


def test_repo_map_sources_exist():
    entries = drift_check.load_map(drift_check.DEFAULT_MAP)
    assert entries
    for entry in entries:
        assert (drift_check.ROOT / entry["crepidoma"]).is_file(), entry["crepidoma"]
