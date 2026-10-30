import itertools
import os
import random
import subprocess
import sys
from pathlib import Path

import pytest
import read_range


def make(tmp_path, count=100):
    path = tmp_path / "f.txt"
    path.write_text("\n".join(f"line{n}" for n in range(1, count + 1)) + "\n", encoding="utf-8")
    return str(path)


def test_prints_numbered_range(tmp_path, capsys):
    assert read_range.main([make(tmp_path), "2", "3"]) == 0
    assert capsys.readouterr().out == "2\tline2\n3\tline3\n"


def test_sixty_lines_allowed_sixty_one_refused(tmp_path, capsys):
    path = make(tmp_path)
    assert read_range.main([path, "1", "60"]) == 0
    assert len(capsys.readouterr().out.splitlines()) == 60
    assert read_range.main([path, "1", "61"]) == 2
    assert "exceeds 60" in capsys.readouterr().err


def test_end_past_file_is_clamped_and_bad_args_fail(tmp_path, capsys):
    path = make(tmp_path, 3)
    assert read_range.main([path, "2", "9"]) == 0
    assert len(capsys.readouterr().out.splitlines()) == 2
    assert read_range.main([path, "5", "2"]) == 2
    assert read_range.main([path, "a", "2"]) == 2
    assert read_range.main([str(tmp_path / "none"), "1", "2"]) == 1


@pytest.mark.parametrize(
    ("tokens", "expected"),
    [
        (["10-40"], [(10, 40)]),
        (["10", "40"], [(10, 40)]),
        (["1-5", "7", "9", "20-30"], [(1, 5), (7, 9), (20, 30)]),
    ],
)
def test_parse_specs_valid(tokens, expected):
    assert read_range.parse_specs(tokens) == expected


@pytest.mark.parametrize(
    "tokens",
    [
        [],
        ["5"],
        ["a-b"],
        ["0-3"],
        ["5-2"],
        ["3", "1"],
        ["1-", "2"],
        ["1", "2-3"],
        ["-1-3"],
        ["\u0661-\u0662"],
    ],
)
def test_parse_specs_invalid(tokens):
    with pytest.raises(ValueError):
        read_range.parse_specs(tokens)


@pytest.mark.parametrize(
    ("ranges", "expected"),
    [
        ([(5, 9), (1, 3)], [(1, 3), (5, 9)]),
        ([(1, 3), (4, 6)], [(1, 6)]),
        ([(1, 10), (3, 4)], [(1, 10)]),
        ([(1, 5), (5, 8), (20, 21)], [(1, 8), (20, 21)]),
    ],
)
def test_merge_cases(ranges, expected):
    assert read_range.merge_ranges(ranges) == expected


def test_merge_properties_random():
    rng = random.Random(7)  # noqa: S311
    for _ in range(300):
        ranges = []
        for _ in range(rng.randint(1, 8)):
            start = rng.randint(1, 60)
            ranges.append((start, start + rng.randint(0, 15)))
        merged = read_range.merge_ranges(ranges)
        covered = {n for s, e in ranges for n in range(s, e + 1)}
        assert {n for s, e in merged for n in range(s, e + 1)} == covered
        assert all(a[1] + 1 < b[0] for a, b in itertools.pairwise(merged))
        assert all(s <= e for s, e in merged)
        assert read_range.merge_ranges(merged) == merged
        assert read_range.merge_ranges(ranges[::-1]) == merged


def test_multi_range_with_header_and_merge(tmp_path, capsys):
    path = make(tmp_path)
    assert read_range.main([path, "1-2", "3-4", "10", "11"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == f"== {path}:1-4 =="
    assert out[1] == "1\tline1"
    assert f"== {path}:10-11 ==" in out
    assert len(out) == 1 + 4 + 1 + 2


def test_multi_file(tmp_path, capsys):
    a = make(tmp_path, 5)
    b = tmp_path / "g.txt"
    b.write_text("x\ny\n", encoding="utf-8")
    assert read_range.main([a, "2-3", "--", str(b), "1-2"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out == [f"== {a}:2-3 ==", "2\tline2", "3\tline3", f"== {b}:1-2 ==", "1\tx", "2\ty"]


def test_combined_cap_truncates(tmp_path, capsys):
    path = make(tmp_path, 200)
    assert read_range.main([path, "1-40", "100-140"]) == 0
    out = capsys.readouterr().out.splitlines()
    numbered = [line for line in out if not line.startswith("==") and "\t" in line]
    assert len(numbered) == 60
    assert out[-1] == "... truncated: 21 more lines requested"
    assert read_range.main([path, "1-60", "70-75"]) == 0
    assert capsys.readouterr().out.splitlines()[-1] == "... truncated: 6 more lines requested"


def test_multi_errors(tmp_path):
    path = make(tmp_path, 3)
    assert read_range.main([path, "1-2", "--"]) == 2
    assert read_range.main([path, "x-2"]) == 2
    assert read_range.main([path, "1-2", "--", str(tmp_path / "none"), "1-2"]) == 1


def test_prints_characters_the_console_code_page_lacks(tmp_path):
    # A Windows console defaults to a legacy code page; arrows and CJK
    # used to raise UnicodeEncodeError.
    path = tmp_path / "u.txt"
    path.write_text("a → b 日本\n", encoding="utf-8")
    env = {**os.environ, "PYTHONIOENCODING": "cp1250"}
    script = Path(read_range.__file__)
    done = subprocess.run(
        [sys.executable, str(script), str(path), "1", "1"], capture_output=True, env=env
    )
    assert done.returncode == 0, done.stderr.decode("utf-8", "replace")
    assert done.stdout.decode("utf-8").splitlines() == ["1\ta → b 日本"]


def test_multi_range_form_also_prints_utf8_on_a_legacy_code_page(tmp_path):
    path = tmp_path / "u.txt"
    path.write_text("a → b\n日本\n", encoding="utf-8")
    env = {**os.environ, "PYTHONIOENCODING": "cp1250"}
    script = Path(read_range.__file__)
    done = subprocess.run(
        [sys.executable, str(script), str(path), "1-1", "2-2"], capture_output=True, env=env
    )
    assert done.returncode == 0, done.stderr.decode("utf-8", "replace")
    assert "日本" in done.stdout.decode("utf-8")
