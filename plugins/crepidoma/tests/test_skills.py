import re
from pathlib import Path

SKILLS = Path(__file__).resolve().parent.parent / "skills"
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def test_docs_sweep_skill_declares_name_and_description():
    text = (SKILLS / "docs-sweep" / "SKILL.md").read_text(encoding="utf-8")
    match = FRONTMATTER.match(text)
    assert match
    assert "name: docs-sweep" in match.group(1)
    assert "description:" in match.group(1)
    for needle in ("graphify", "haiku", "token", "scout"):
        assert needle in text.lower(), needle


def test_migrate_pillar_skill_uses_the_migrator_agent():
    text = (SKILLS / "migrate-pillar" / "SKILL.md").read_text(encoding="utf-8")
    assert FRONTMATTER.match(text)
    assert "pillar-migrator" in text
    assert (SKILLS.parent / "agents" / "pillar-migrator.md").is_file()
