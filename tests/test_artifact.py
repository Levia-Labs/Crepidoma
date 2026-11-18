import copy
import json
import re
from pathlib import Path

import artifact
import artifact_examples
import artifact_spec
import pytest

EXAMPLE = Path(artifact.KIT) / "example.json"


def graph_spec(**changes):
    spec = artifact_examples.example("graph")
    spec["sections"][0].update(changes)
    return spec


def errors_of(spec):
    return artifact_spec.validate(spec)


def build(tmp_path, spec, *flags):
    src = tmp_path / "page.json"
    src.write_text(json.dumps(spec), encoding="utf-8")
    code = artifact.main(["build", str(src), *flags])
    return code, tmp_path / "page.html"


def test_example_spec_is_valid():
    assert errors_of(json.loads(EXAMPLE.read_text(encoding="utf-8"))) == []


@pytest.mark.parametrize("kind", artifact.KINDS)
def test_new_examples_are_valid(kind):
    assert errors_of(artifact_examples.example(kind)) == []


def test_unknown_section_type():
    spec = {"title": "Page", "sections": [{"type": "chart", "title": "x"}]}
    assert errors_of(spec) == ["spec:sections[0].type: unknown section type 'chart'"]


def test_unknown_field_names_its_path():
    spec = graph_spec()
    spec["sections"][0]["nodes"][1]["colour"] = "red"
    assert errors_of(spec) == ["spec:sections[0].nodes[1].colour: unknown field 'colour'"]


def test_duplicate_node_ids():
    spec = graph_spec()
    spec["sections"][0]["nodes"].append({"id": "plan", "label": "Again", "category": "a"})
    assert errors_of(spec) == ["spec:sections[0].nodes[3].id: duplicate node id 'plan'"]


def test_duplicate_section_ids():
    spec = artifact_examples.example("cards")
    spec["sections"] = [
        {**spec["sections"][0], "id": "same"},
        {**spec["sections"][0], "id": "same"},
    ]
    assert errors_of(spec) == ["spec:sections[1].id: duplicate section id 'same'"]


def test_edge_to_missing_node():
    spec = graph_spec(edges=[["plan", "ghost"]])
    assert errors_of(spec) == ["spec:sections[0].edges[0]: edge names missing node 'ghost'"]


def test_cycle_is_reported():
    spec = graph_spec(edges=[["plan", "build"], ["build", "ship"], ["ship", "build"]])
    assert errors_of(spec) == ["spec:sections[0].edges: cycle through build, ship"]


def test_self_edge_is_a_cycle():
    assert errors_of(graph_spec(edges=[["plan", "plan"]])) == [
        "spec:sections[0].edges: cycle through plan"
    ]


def test_missing_start_node():
    assert errors_of(graph_spec(start="nope")) == [
        "spec:sections[0].start: start names missing node 'nope'"
    ]


def test_unknown_category():
    spec = graph_spec()
    spec["sections"][0]["nodes"][0]["category"] = "zzz"
    assert errors_of(spec) == ["spec:sections[0].nodes[0].category: unknown category 'zzz'"]


def test_bad_tone():
    spec = artifact_examples.example("cards")
    spec["sections"][0]["items"][0]["tone"] = "purple"
    (line,) = errors_of(spec)
    assert line.startswith("spec:sections[0].items[0].tone: bad tone 'purple'")


def test_board_item_with_unknown_status():
    spec = artifact_examples.example("board")
    spec["sections"][0]["bands"][0]["groups"][0]["items"][0]["status"] = "lost"
    assert errors_of(spec) == [
        "spec:sections[0].bands[0].groups[0].items[0].status: unknown status 'lost'"
    ]


def test_timeline_bar_past_last_unit():
    spec = artifact_examples.example("timeline")
    spec["sections"][0]["rows"][1]["span"] = 5
    (line,) = errors_of(spec)
    assert line.startswith("spec:sections[0].rows[1]: bar ends at unit 7")


def test_timeline_target_must_be_a_section():
    spec = artifact_examples.example("timeline")
    spec["sections"][0]["rows"][0]["target"] = "elsewhere"
    assert errors_of(spec) == ["spec:sections[0].rows[0].target: unknown section id 'elsewhere'"]


@pytest.mark.parametrize(
    "title", ["One two three four five", "Graph - dependencies", "Graph: dependencies"]
)
def test_bad_titles(title):
    spec = artifact_examples.example("cards")
    spec["title"] = title
    (line,) = errors_of(spec)
    assert line.startswith("spec:title:")


def test_hyphenated_title_is_fine():
    spec = artifact_examples.example("cards")
    spec["title"] = "Follow-up plan"
    assert errors_of(spec) == []


def test_invalid_spec_exits_one_and_writes_nothing(tmp_path, capsys):
    code, out = build(tmp_path, graph_spec(start="nope"))
    assert code == 1
    assert not out.exists()
    assert capsys.readouterr().err.startswith("spec:sections[0].start:")


def test_unreadable_json_exits_one(tmp_path, capsys):
    src = tmp_path / "bad.json"
    src.write_text("{", encoding="utf-8")
    assert artifact.main(["build", str(src)]) == 1
    assert capsys.readouterr().err.startswith("spec:$:")


def test_script_tags_in_text_cannot_close_the_data_script(tmp_path):
    spec = artifact_examples.example("cards")
    spec["sections"][0]["items"][0]["body"] = "</script><script>alert(1)</script><!--"
    code, out = build(tmp_path, spec)
    page = out.read_text(encoding="utf-8")
    payload = re.search(r'id="artifact-data">(.*?)</script>', page, re.S).group(1)
    assert code == 0
    assert "<" not in payload
    assert (
        json.loads(payload)["sections"][0]["items"][0]["body"]
        == spec["sections"][0]["items"][0]["body"]
    )
    assert page.count("<script") == 2


def test_title_is_html_escaped(tmp_path):
    spec = artifact_examples.example("cards")
    spec["title"] = "Fish & <chips>"
    _, out = build(tmp_path, spec)
    assert "<title>Fish &amp; &lt;chips&gt;</title>" in out.read_text(encoding="utf-8")


def test_inline_marks_stay_text_in_data_and_render_through_dom(tmp_path):
    spec = artifact_examples.example("cards")
    _, out = build(tmp_path, spec)
    page = out.read_text(encoding="utf-8")
    assert "**bold** and `code`" in page
    assert 'el("strong"' in page and 'el("code"' in page


def test_kit_scripts_never_use_innerhtml():
    for path in Path(artifact.KIT).glob("*.js"):
        text = path.read_text(encoding="utf-8")
        assert "innerHTML" not in text, path.name
        assert "</" not in text, path.name


def test_fragment_shape(tmp_path):
    _, out = build(tmp_path, artifact_examples.example("cards"))
    page = out.read_text(encoding="utf-8")
    assert page.startswith("<title>Sample page</title>\n")
    assert '<meta name="claude:viewport-fit-sides" content="cover">' in page
    assert "fonts.googleapis.com/css2" in page
    for tag in ("<!doctype", "<html", "<head", "<body"):
        assert tag not in page.lower()


def test_standalone_shape(tmp_path):
    _, out = build(tmp_path, artifact_examples.example("cards"), "--standalone")
    page = out.read_text(encoding="utf-8")
    assert page.startswith('<!doctype html>\n<html lang="en"><head>')
    assert '<meta charset="utf-8">' in page
    assert "viewport-fit=cover" in page
    assert "<title>Sample page</title>" in page
    assert page.rstrip().endswith("</body></html>")


def test_only_needed_scripts_are_included(tmp_path):
    _, out = build(tmp_path, artifact_examples.example("cards"))
    page = out.read_text(encoding="utf-8")
    assert "R.types.cards" in page
    for other in ("R.types.graph", "R.types.board", "R.types.timeline", "R.types.prose"):
        assert other not in page


def test_graph_page_includes_graph_script(tmp_path):
    _, out = build(tmp_path, artifact_examples.example("graph"))
    assert "R.types.graph" in out.read_text(encoding="utf-8")


def test_css_has_no_literal_colours_in_components():
    css = (Path(artifact.KIT) / "kit.css").read_text(encoding="utf-8")
    components = css[css.index("*{box-sizing") :]
    assert not re.search(r"#[0-9A-Fa-f]{3,8}\b|rgba?\(", components)


def test_css_dark_blocks_match_token_names():
    css = (Path(artifact.KIT) / "kit.css").read_text(encoding="utf-8")
    light, rest = css.split("@media (prefers-color-scheme: dark)")
    media, forced = rest.split(':root[data-theme="dark"]')
    forced = forced.split("*{box-sizing")[0]
    names = set(re.findall(r"(--[a-z0-9-]+):#", light))
    assert names
    assert set(re.findall(r"(--[a-z0-9-]+):#", media)) == names
    assert set(re.findall(r"(--[a-z0-9-]+):#", forced)) == names
    assert "color-scheme:dark" in media and "color-scheme:dark" in forced


def test_example_builds_standalone(tmp_path, capsys):
    spec = copy.deepcopy(json.loads(EXAMPLE.read_text(encoding="utf-8")))
    code, out = build(tmp_path, spec, "--standalone")
    assert code == 0
    assert re.fullmatch(
        r"artifact build: .*page\.html \d+ B, 3 sections\n", capsys.readouterr().out
    )
    assert "R.types.timeline" in out.read_text(encoding="utf-8")


def test_output_flag_chooses_path(tmp_path):
    src = tmp_path / "s.json"
    src.write_text(json.dumps(artifact_examples.example("cards")), encoding="utf-8")
    target = tmp_path / "custom.html"
    assert artifact.main(["build", str(src), "-o", str(target)]) == 0
    assert target.exists()


def test_new_writes_a_buildable_spec(tmp_path):
    out = tmp_path / "g.json"
    assert artifact.main(["new", str(out), "--kind", "graph"]) == 0
    spec = json.loads(out.read_text(encoding="utf-8"))
    assert spec["sections"][0]["start"] in {n["id"] for n in spec["sections"][0]["nodes"]}


def test_new_refuses_to_overwrite(tmp_path, capsys):
    out = tmp_path / "g.json"
    out.write_text("keep", encoding="utf-8")
    assert artifact.main(["new", str(out)]) == 1
    assert out.read_text(encoding="utf-8") == "keep"
    assert "not overwriting" in capsys.readouterr().err


def test_check_delegates_to_artifact_check(monkeypatch, tmp_path):
    import sys
    import types

    calls = []
    fake = types.ModuleType("artifact_check")
    fake.main = lambda argv=None: calls.append(argv) or 7
    monkeypatch.setitem(sys.modules, "artifact_check", fake)
    page = tmp_path / "p.html"
    assert artifact.main(["check", str(page)]) == 7
    assert calls == [[str(page)]]
