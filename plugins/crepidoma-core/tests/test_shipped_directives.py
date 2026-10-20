import inject_directives as inj

EXPECTED = {
    "10-communication-style.md",
    "20-tool-first-loop.md",
    "30-conventions.md",
    "40-models.md",
    "50-skills-and-plugins.md",
    "60-taskfile-shell.md",
}


def test_shipped_directives_present_and_fit():
    names = {path.name for path in inj.DIRECTIVES.glob("*.md")}
    assert names == EXPECTED
    text = inj.build(inj.DIRECTIVES)
    assert 0 < len(text) <= inj.LIMIT


def test_no_user_scope_paths():
    text = inj.build(inj.DIRECTIVES)
    assert "~/.claude/bin" not in text
