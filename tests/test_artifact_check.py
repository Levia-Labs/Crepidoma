import pathlib

import artifact_check as ac
import pytest

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "artifact"
GOOD = (FIXTURES / "good.html").read_text(encoding="utf-8")
DARK_ATTR = ':root[data-theme="dark"] { --bg: #111; --ink: #eee; color-scheme: dark; }'


def rules(html, size=None):
    return [f.rule for f in ac.lint(html, size)]


def sub(old, new):
    assert old in GOOD
    return GOOD.replace(old, new)


def test_good_fixture_is_clean():
    assert ac.lint(GOOD) == []


@pytest.mark.parametrize(
    ("title", "severity"),
    [
        ("Plan: details", "error"),
        ("Plan - details", "error"),
        (f"Plan {chr(0x2013)} details", "error"),
        (f"Plan {chr(0x2014)} details", "error"),
        ("one two three four five six", "warning"),
    ],
)
def test_title_findings(title, severity):
    found = [f for f in ac.lint(sub("Rail network plan", title)) if f.rule == "title"]
    assert [f.severity for f in found] == [severity]


def test_missing_title_is_error():
    found = ac.lint(sub("<title>Rail network plan</title>", ""))
    assert [(f.rule, f.severity) for f in found] == [("title", "error")]


def test_title_past_8kb_is_missing():
    assert "title" in rules("<p>" + "x" * 9000 + "</p>" + GOOD)


def test_script_host_outside_allow_list():
    assert "script-host" in rules(sub("cdn.jsdelivr.net/npm/", "evil.example/"))


@pytest.mark.parametrize("path", ["chart.js@latest/x.js", "chart.js@4/x.js", "chart.js/x.js"])
def test_script_pin_requires_exact_version(path):
    assert "script-pin" in rules(sub("chart.js@4.4.1/dist/chart.umd.min.js", path))


def test_tailwind_cdn_needs_no_pin():
    assert rules(GOOD + '<script src="https://cdn.tailwindcss.com"></script>') == []


def test_stylesheet_host_outside_fonts():
    assert "stylesheet-host" in rules(sub("fonts.googleapis.com", "evil.example"))


def test_import_of_other_host():
    html = sub("body {", '@import url("https://evil.example/a.css");\nbody {')
    assert "stylesheet-host" in rules(html)


def test_import_of_fonts_host_passes():
    html = sub("body {", '@import url("https://fonts.googleapis.com/css2?family=A");\nbody {')
    assert rules(html) == []


def test_dark_token_missing_on_root():
    assert "theme-tokens" in rules(sub("--bg: #fff; --ink: #111;", "--bg: #fff;"))


def test_only_one_dark_block():
    assert "theme-tokens" in rules(sub(DARK_ATTR, ""))


def test_dark_block_without_color_scheme():
    assert "theme-tokens" in rules(sub(DARK_ATTR, DARK_ATTR.replace(" color-scheme: dark;", "")))


def test_dark_blocks_with_different_tokens():
    assert "theme-tokens" in rules(sub(DARK_ATTR, DARK_ATTR.replace(" --ink: #eee;", "")))


def test_literal_colour_in_rule():
    found = ac.lint(sub("body {", "a { color: #abcdef; }\nbody {"))
    assert [(f.rule, f.severity) for f in found] == [("literal-colour", "warning")]


def test_colour_keywords_pass():
    assert (
        rules(
            sub("body {", "a { color: currentColor; fill: none; border: 0 transparent; }\nbody {")
        )
        == []
    )


def test_literal_colour_in_inline_style_and_svg():
    html = GOOD + '<p style="color: rgb(1,2,3)">x</p><svg><path fill="#fff" stroke="none"/></svg>'
    assert rules(html).count("literal-colour") == 2


def test_body_without_background():
    assert "body-background" in rules(sub("body { background: var(--bg);", "body {"))


def test_gutter_missing_right_padding():
    html = sub("max(16px, env(safe-area-inset-right", "max(8px, env(safe-area-inset-right")
    found = [f for f in ac.lint(html) if f.rule == "side-gutter"]
    assert len(found) == 1
    assert "right" in found[0].message


def test_gutter_only_checked_with_meta():
    html = sub('<meta name="claude:viewport-fit-sides" content="cover">', "")
    assert "side-gutter" not in rules(html.replace("max(16px, env(safe-area-inset-left", "0 (x"))


@pytest.mark.parametrize(
    "snippet",
    [
        "<script>alert(1)</script>",
        "<script>if (confirm('x')) {}</script>",
        "<script>prompt('x')</script>",
        "<script>window.print()</script>",
        "<iframe src='a'></iframe>",
        "<object data='a'></object>",
        "<embed src='a'>",
        "<a href='f.txt' download>f</a>",
        "<form action='/x'></form>",
    ],
)
def test_blocked_api(snippet):
    assert "blocked-api" in rules(GOOD + snippet)


def test_lookalike_calls_pass():
    assert rules(GOOD + "<script>obj.alert(1); myprompt(2)</script><form></form>") == []


def test_storage_outside_try_warns():
    found = ac.lint(GOOD + "<script>localStorage.setItem('a','b')</script>")
    assert [(f.rule, f.severity) for f in found] == [("storage", "warning")]


def test_storage_inside_try_passes():
    assert rules(GOOD + "<script>try { sessionStorage.getItem('a') } catch (e) {}</script>") == []


def test_viewport_height_warns():
    assert "viewport-height" in rules(sub("body {", "main { min-height: 100vh; }\nbody {"))


def test_own_skeleton_warns_only_when_leading():
    assert "own-skeleton" in rules("<!DOCTYPE html>\n" + GOOD)
    assert "own-skeleton" in rules("  <html>" + GOOD)
    assert "own-skeleton" not in rules(GOOD)


def test_skeleton_style_block_is_not_counted_as_literal_colour():
    skeleton = "<!doctype html><style>body{background:#fff;color:#000}</style>"
    assert "literal-colour" not in rules(skeleton + GOOD)


def test_size_above_16mb_is_error():
    assert "size" in rules(GOOD, size=16 * 1024 * 1024 + 1)
    assert "size" not in rules(GOOD, size=16 * 1024 * 1024)


def test_em_dash_in_visible_text_only():
    assert "em-dash" in rules(GOOD + "<p>a — b</p>")
    assert "em-dash" not in rules(GOOD + "<!-- — --><script>var s = '—'</script>")


def test_line_numbers_follow_the_source():
    found = [f for f in ac.lint(GOOD + "\n<p>a — b</p>") if f.rule == "em-dash"]
    assert found[0].line == GOOD.count("\n") + 2


def test_main_clean_file_exits_zero(tmp_path, capsys):
    page = tmp_path / "a.html"
    page.write_text(GOOD, encoding="utf-8")
    assert ac.main([str(page)]) == 0
    assert capsys.readouterr().out == "artifact check: 1 files, 0 errors, 0 warnings\n"


def test_main_reports_findings_and_exits_one(capsys):
    assert ac.main([str(FIXTURES / "bad.html"), str(FIXTURES / "good.html")]) == 1
    out = capsys.readouterr().out.splitlines()
    assert any(
        line.endswith("error script-host: script host not allowed: https://evil.example/x.js")
        for line in out
    )
    assert any(": warning own-skeleton:" in line for line in out)
    assert out[-1].startswith("artifact check: 2 files, ")


def test_main_warnings_alone_exit_zero(tmp_path, capsys):
    page = tmp_path / "a.html"
    page.write_text(GOOD + "<style>main{height:100vh}</style>", encoding="utf-8")
    assert ac.main([str(page)]) == 0
    assert "0 errors, 1 warnings" in capsys.readouterr().out


def test_main_missing_file_is_error(tmp_path, capsys):
    assert ac.main([str(tmp_path / "none.html")]) == 1
    assert "error read:" in capsys.readouterr().out


def test_main_caps_output_at_40_lines(tmp_path, capsys):
    page = tmp_path / "a.html"
    page.write_text(GOOD + "<style>a{height:100vh}</style>" * 55, encoding="utf-8")
    ac.main([str(page)])
    out = capsys.readouterr().out.splitlines()
    assert len(out) == 42
    assert out[40] == "... 15 more"


def test_inert_json_data_block_is_not_linted():
    block = (
        '<script type="application/json" id="artifact-data">{"t":"alert(1) localStorage"}</script>'
    )
    html = sub("<h1>Plan</h1>", "<h1>Plan</h1>" + block)
    assert "blocked-api" not in rules(html)
    assert "storage" not in rules(html)
    run = sub("<h1>Plan</h1>", "<h1>Plan</h1><script>alert(1)</script>")
    assert "blocked-api" in rules(run)
