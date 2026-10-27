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
