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


def test_mirror_entries_expect_identical_copies(tmp_path: Path):
    root, pillar = tmp_path / "crep", tmp_path / "pillar"
    make(root / "configs/.editorconfig", b"root = true\n")
    make(pillar / ".editorconfig", b"root = true\n")
    make(root / "configs/.yamllint", b"a\n")
    make(pillar / ".yamllint", b"b\n")
    entries = [
        {"crepidoma": "configs/.editorconfig", "pillar": [".editorconfig"], "mirror": True},
        {"crepidoma": "configs/.yamllint", "pillar": [".yamllint"], "mirror": True},
    ]
    assert drift_check.check(pillar, entries, root) == [
        ("mirror", "configs/.editorconfig", ".editorconfig"),
        ("drifted", "configs/.yamllint", ".yamllint"),
    ]


def declare(pillar: Path, body: str) -> None:
    make(pillar / ".crepidoma-drift.toml", body.encode())


def state(pillar: Path, entries: list[dict], root: Path) -> str:
    return drift_check.check(pillar, entries, root)[0][0]


def test_extended_line_file(tmp_path: Path):
    root, pillar = tmp_path / "crep", tmp_path / "pillar"
    make(root / "c/.ga", b"* text=auto\n*.png   binary\n")
    make(pillar / ".ga", b"* text=auto\r\n*.png binary\n*.cs text\n")
    entries = [{"crepidoma": "c/.ga", "pillar": [".ga"], "mirror": True}]
    assert state(pillar, entries, root) == "drifted"
    declare(pillar, '[[extended]]\npath = ".ga"\n')
    assert state(pillar, entries, root) == "extended"


def test_extended_requires_shared_content(tmp_path: Path):
    root, pillar = tmp_path / "crep", tmp_path / "pillar"
    make(root / "c/.ga", b"a\nb\n")
    make(pillar / ".ga", b"a\nc\n")
    entries = [{"crepidoma": "c/.ga", "pillar": [".ga"]}]
    declare(pillar, '[[extended]]\npath = ".ga"\n')
    assert state(pillar, entries, root) == "drifted"
    declare(pillar, '[[extended]]\npath = ".ga"\nwaive = ["b"]\n')
    assert state(pillar, entries, root) == "extended"


def test_extended_yaml(tmp_path: Path):
    root, pillar = tmp_path / "crep", tmp_path / "pillar"
    make(root / "c/sg.yml", b"ruleDirs:\n  - a\nname: x\n")
    entries = [{"crepidoma": "c/sg.yml", "pillar": ["sg.yml"]}]
    declare(pillar, '[[extended]]\npath = "sg.yml"\n')
    make(pillar / "sg.yml", b"# c\nruleDirs:\n  - a\n  - b\nname: x\ntests:\n  - t: 1\n")
    assert state(pillar, entries, root) == "extended"
    make(pillar / "sg.yml", b"ruleDirs:\n  - b\nname: x\n")
    assert state(pillar, entries, root) == "drifted"
    make(pillar / "sg.yml", b"ruleDirs:\n  - a\nname: y\n")
    assert state(pillar, entries, root) == "drifted"
    declare(pillar, '[[extended]]\npath = "sg.yml"\nwaive = ["name|name: x"]\n')
    assert state(pillar, entries, root) == "extended"
