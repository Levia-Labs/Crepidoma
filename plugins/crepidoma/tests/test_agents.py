import re
from pathlib import Path

AGENTS = Path(__file__).resolve().parent.parent / "agents"
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def frontmatter(path: Path) -> dict[str, str]:
    match = FRONTMATTER.match(path.read_text(encoding="utf-8"))
    assert match, path.name
    fields = {}
    for line in match.group(1).splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def test_agents_have_required_fields_and_unique_names():
    files = sorted(AGENTS.glob("*.md"))
    assert len(files) >= 3
    names = []
    for path in files:
        fields = frontmatter(path)
        assert fields.get("name") == path.stem
        assert fields.get("description")
        assert fields.get("tools"), "agents carry only the tools they use"
        names.append(fields["name"])
    assert len(names) == len(set(names))


def test_haiku_scout_is_read_only():
    fields = frontmatter(AGENTS / "scout.md")
    assert fields["model"] == "haiku"
    tools = {tool.strip() for tool in fields["tools"].split(",")}
    assert tools <= {"Read", "Grep", "Glob"}


def test_work_agents_run_on_sonnet():
    for path in AGENTS.glob("*.md"):
        if path.stem != "scout":
            assert frontmatter(path)["model"] == "sonnet", path.name
