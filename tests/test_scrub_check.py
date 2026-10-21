from pathlib import Path

import scrub_check

DRIVE = "C" + ":"
PROJECTS = "X" + ":/Projects/thing"


def test_clean_text_has_no_hits():
    assert scrub_check.scan_text("plain words\nmore words\n", None) == []


def test_windows_user_path_hit():
    text = f"see {DRIVE}\\Users\\someone\\notes\n"
    assert scrub_check.scan_text(text, None) == [(1, "windows-user-path")]


def test_projects_drive_path_hit():
    assert scrub_check.scan_text(PROJECTS + "\n", None) == [(1, "local-projects-path")]


def test_posix_home_hit_but_not_url_or_tilde():
    home = "/ho" + "me/someone/x"
    assert scrub_check.scan_text(f"cd {home}\n", None) == [(1, "posix-home-path")]
    assert scrub_check.scan_text("see https://example.com/Users/x and ~/.claude\n", None) == []


def test_email_hit_and_allowlist():
    addr = "someone" + "@" + "corp.io"
    assert scrub_check.scan_text(f"mail {addr}\n", None) == [(1, "email")]
    bot = "noreply" + "@" + "anthropic.com"
    ssh = "git" + "@" + "github.com:Org/Repo.git"
    assert scrub_check.scan_text(f"by <{bot}> via {ssh}\n", None) == []


def test_token_hit():
    token = "gh" + "p_" + "a" * 36
    assert scrub_check.scan_text(f"t={token}\n", None) == [(1, "token")]


def test_denylist_word_boundary(tmp_path: Path):
    deny_file = tmp_path / "deny"
    deny_file.write_text("# comment\nsecretproj\n", encoding="utf-8")
    deny = scrub_check.load_denylist(deny_file)
    assert scrub_check.scan_text("about SecretProj today\n", deny) == [(1, "denylisted-name")]
    assert scrub_check.scan_text("secretprojects\n", deny) == []


def test_allow_marker_skips_line():
    assert scrub_check.scan_text(PROJECTS + "  scrub" + ":allow\n", None) == []


def test_missing_or_empty_denylist_is_none(tmp_path: Path):
    assert scrub_check.load_denylist(tmp_path / "absent") is None
    empty = tmp_path / "empty"
    empty.write_text("# only comments\n", encoding="utf-8")
    assert scrub_check.load_denylist(empty) is None


def test_binary_file_skipped(tmp_path: Path):
    blob = tmp_path / "blob.bin"
    blob.write_bytes(b"\xff\xfe\x00\x81")
    assert scrub_check.scan_file(blob, None) == []


def test_crlf_line_numbers(tmp_path: Path):
    target = tmp_path / "a.txt"
    target.write_bytes(b"ok\r\n" + (PROJECTS + "\r\n").encode())
    assert scrub_check.scan_file(target, None) == [(2, "local-projects-path")]


def test_main_exit_codes(tmp_path: Path, capsys):
    clean = tmp_path / "clean.md"
    clean.write_text("fine\n", encoding="utf-8")
    dirty = tmp_path / "dirty.md"
    dirty.write_text(PROJECTS + "\n", encoding="utf-8")
    none = str(tmp_path / "none")
    assert scrub_check.main(["--denylist", none, str(clean)]) == 0
    assert scrub_check.main(["--denylist", none, str(dirty)]) == 1
    assert "dirty.md:1: local-projects-path" in capsys.readouterr().out


def _deny_file(tmp_path: Path) -> Path:
    deny_file = tmp_path / "deny"
    deny_file.write_text("secret-pillar\n", encoding="utf-8")
    return deny_file


def test_commit_message_with_denylisted_name_fails(tmp_path: Path, capsys):
    msg = tmp_path / "COMMIT_EDITMSG"
    msg.write_text("feat: port\n\nCopied from secret-pillar.\n", encoding="utf-8")
    assert scrub_check.main(["--denylist", str(_deny_file(tmp_path)), str(msg)]) == 1
    assert "COMMIT_EDITMSG:3: denylisted-name" in capsys.readouterr().out


def test_clean_commit_message_passes(tmp_path: Path):
    msg = tmp_path / "COMMIT_EDITMSG"
    msg.write_text("feat: port\n\nNothing private.\n", encoding="utf-8")
    assert scrub_check.main(["--denylist", str(_deny_file(tmp_path)), str(msg)]) == 0


def test_strict_missing_file_is_usage_error(tmp_path: Path):
    none = str(tmp_path / "none")
    assert scrub_check.main(["--denylist", none, "--strict", str(tmp_path / "gone.md")]) == 2
    assert scrub_check.main(["--denylist", none, str(tmp_path / "gone.md")]) == 0
