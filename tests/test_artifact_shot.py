import struct
import subprocess
from pathlib import Path

import artifact
import artifact_shot
import pytest

PNG = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", 1280, 900)


@pytest.fixture
def browser(tmp_path, monkeypatch):
    exe = tmp_path / "browser.exe"
    exe.write_text("x", encoding="utf-8")
    monkeypatch.setenv("ARTIFACT_BROWSER", str(exe))
    return exe


@pytest.fixture
def fake_run(monkeypatch):
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        shot = next(a for a in argv if a.startswith("--screenshot="))
        Path(shot.split("=", 1)[1]).write_bytes(PNG)
        page = Path(argv[-1].removeprefix("file:///").removeprefix("file://"))
        calls.append(page.read_text(encoding="utf-8") if page.exists() else "")
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(subprocess, "run", run)
    return calls


def test_argv_shape(tmp_path, browser, fake_run):
    page = tmp_path / "p.html"
    page.write_text("<title>T</title>", encoding="utf-8")
    assert artifact_shot.main([str(page), "--out", str(tmp_path / "o.png"), "--width", "400"]) == 0
    argv = fake_run[0]
    assert argv[0] == str(browser)
    assert "--headless=new" in argv
    assert "--window-size=400,4000" in argv
    assert "--virtual-time-budget=4000" in argv
    assert argv[-1].startswith("file:///")


def test_receipt_reports_png_size_and_theme(tmp_path, browser, fake_run, capsys):
    page = tmp_path / "p.html"
    page.write_text("<title>T</title>", encoding="utf-8")
    out = tmp_path / "o.png"
    assert artifact.main(["shot", str(page), "--out", str(out), "--theme", "dark"]) == 0
    assert capsys.readouterr().out == f"artifact shot: {out} 1280x900 dark\n"


def test_fragment_is_wrapped_with_theme():
    text = artifact_shot.themed("<title>T</title><p>x</p>", "dark")
    assert text.startswith('<!doctype html>\n<html data-theme="dark"')
    assert "<p>x</p>" in text
    assert text.rstrip().endswith("</body></html>")


def test_standalone_page_gets_theme_attribute():
    page = '<!doctype html>\n<html lang="en"><head></head><body></body></html>'
    assert '<html data-theme="light" lang="en">' in artifact_shot.themed(page, "light")


def test_existing_theme_attribute_is_replaced():
    page = '<html data-theme="light" lang="en"></html>'
    text = artifact_shot.themed(page, "dark")
    assert text.count("data-theme") == 1
    assert 'data-theme="dark"' in text


def test_system_theme_leaves_a_standalone_page_alone():
    page = '<html lang="en"></html>'
    assert artifact_shot.themed(page, "system") == page


def test_shot_shoots_a_themed_copy_not_the_page(tmp_path, browser, fake_run):
    page = tmp_path / "p.html"
    page.write_text("<title>T</title>", encoding="utf-8")
    artifact_shot.main([str(page), "--out", str(tmp_path / "o.png"), "--theme", "dark"])
    assert 'data-theme="dark"' in fake_run[1]
    assert page.read_text(encoding="utf-8") == "<title>T</title>"


def test_missing_browser_is_a_clear_error(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ARTIFACT_BROWSER", str(tmp_path / "nope"))
    page = tmp_path / "p.html"
    page.write_text("<title>T</title>", encoding="utf-8")
    assert artifact_shot.main([str(page), "--out", str(tmp_path / "o.png")]) == 1
    assert "ARTIFACT_BROWSER" in capsys.readouterr().err


def test_no_browser_anywhere_names_the_env_var(monkeypatch):
    monkeypatch.delenv("ARTIFACT_BROWSER", raising=False)
    monkeypatch.setattr(artifact_shot, "WINDOWS", [])
    monkeypatch.setattr(artifact_shot, "MAC", [])
    monkeypatch.setattr(artifact_shot.shutil, "which", lambda name: None)
    with pytest.raises(FileNotFoundError, match="ARTIFACT_BROWSER"):
        artifact_shot.find_browser()


def test_failing_browser_exit_is_reported(tmp_path, browser, monkeypatch, capsys):
    monkeypatch.setattr(
        subprocess, "run", lambda argv, **kw: subprocess.CompletedProcess(argv, 3, "", "boom")
    )
    page = tmp_path / "p.html"
    page.write_text("<title>T</title>", encoding="utf-8")
    assert artifact_shot.main([str(page), "--out", str(tmp_path / "o.png")]) == 1
    assert "exited 3" in capsys.readouterr().err


def test_cell_heat_background_is_not_overridden():
    css = (Path(artifact.KIT) / "kit.css").read_text(encoding="utf-8")
    rule = css[css.index(".cell{") : css.index(".cell.hi")]
    assert "background" not in rule


def test_card_columns_follow_item_count():
    css = (Path(artifact.KIT) / "kit.css").read_text(encoding="utf-8")
    assert ".cards{display:grid;gap:12px;grid-template-columns:repeat(auto-fit," in css


def test_stale_png_is_not_reported_as_success(tmp_path, browser, monkeypatch, capsys):
    monkeypatch.setattr(
        subprocess, "run", lambda argv, **kw: subprocess.CompletedProcess(argv, 0, "", "")
    )
    page = tmp_path / "p.html"
    page.write_text("<title>T</title>", encoding="utf-8")
    out = tmp_path / "o.png"
    out.write_bytes(PNG)
    assert artifact_shot.main([str(page), "--out", str(out)]) == 1
    assert not out.exists()
