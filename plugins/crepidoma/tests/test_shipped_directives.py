import inject_directives as inj

EXPECTED = {
    "10-communication-style.md",
    "20-tool-first-loop.md",
    "30-conventions.md",
    "40-models.md",
    "50-skills-and-plugins.md",
    "60-taskfile-shell.md",
    "70-shell-and-safety.md",
}


def test_shipped_directives_present_and_fit():
    names = {p.name for p in inj.DIRECTIVES.glob("*.md") if p.name != "README.md"}
    assert names == EXPECTED
    text = inj.build(inj.DIRECTIVES)
    assert 0 < len(text) <= inj.LIMIT


def test_no_user_scope_paths():
    text = inj.build(inj.DIRECTIVES)
    assert "~/.claude/bin" not in text


def test_models_directive_names_all_three_tiers():
    text = (inj.DIRECTIVES / "40-models.md").read_text(encoding="utf-8")
    for needle in ("claude-opus-5-5", "sonnet", "haiku", "scout", "95 percent"):
        assert needle in text, needle


def test_absolute_mode_and_style_fallback_present():
    text = (inj.DIRECTIVES / "10-communication-style.md").read_text(encoding="utf-8")
    for needle in ('"one"', "call-to-action", "mirror"):
        assert needle in text, needle


def test_tool_first_covers_skills_lanes_and_history():
    text = (inj.DIRECTIVES / "20-tool-first-loop.md").read_text(encoding="utf-8")
    for needle in ("skill", "retire", "session history"):
        assert needle in text, needle


def test_subagent_harness_is_compact_and_never_caveman():
    text = inj.build(inj.DIRECTIVES / "subagent")
    assert 0 < len(text) <= 1500
    lowered = text.lower()
    assert "never caveman" in lowered
    assert "receipt" in lowered


def test_main_directives_exclude_subagent_harness():
    assert "Subagent harness" not in inj.build(inj.DIRECTIVES)


def test_main_directives_leave_headroom_under_the_cap():
    assert len(inj.build(inj.DIRECTIVES)) <= 8_500
