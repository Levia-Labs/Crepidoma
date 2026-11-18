import json
from pathlib import Path

import artifact
import artifact_budget
import artifact_examples
import artifact_spec
import pytest

GALLERY = Path(artifact.KIT) / "gallery.json"
NEW_KINDS = ["layers", "pivot", "treemap", "sankey", "heatmap"]
BIG = {"type": "cards", "title": "Many", "items": [{"title": "x"}] * 20}


def spec_of(kind, **changes):
    spec = artifact_examples.example(kind)
    spec["sections"][0].update(changes)
    return spec


def errors_of(kind, **changes):
    return artifact_spec.validate(spec_of(kind, **changes))


def test_gallery_is_valid_and_uses_every_section_type():
    spec = json.loads(GALLERY.read_text(encoding="utf-8"))
    assert artifact_spec.validate(spec) == []
    assert {s["type"] for s in spec["sections"]} == set(artifact.SCRIPTS)


def test_gallery_has_no_text_warnings():
    spec = json.loads(GALLERY.read_text(encoding="utf-8"))
    assert artifact_budget.warnings(spec) == []


@pytest.mark.parametrize("kind", NEW_KINDS)
def test_new_kind_examples_are_valid_and_quiet(kind):
    spec = artifact_examples.example(kind)
    assert artifact_spec.validate(spec) == []
    assert artifact_budget.warnings(spec) == []


@pytest.mark.parametrize("kind", NEW_KINDS)
def test_only_the_needed_widget_script_is_included(kind, tmp_path):
    src = tmp_path / "p.json"
    src.write_text(json.dumps(artifact_examples.example(kind)), encoding="utf-8")
    assert artifact.main(["build", str(src)]) == 0
    page = (tmp_path / "p.html").read_text(encoding="utf-8")
    assert f"R.types.{kind} =" in page
    assert sum(f"R.types.{k} =" in page for k in artifact.SCRIPTS) == 1


@pytest.mark.parametrize("kind", NEW_KINDS)
def test_new_cli_writes_each_new_kind(kind, tmp_path):
    out = tmp_path / "n.json"
    assert artifact.main(["new", str(out), "--kind", kind]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["sections"][0]["type"] == kind


@pytest.mark.parametrize("kind", NEW_KINDS)
def test_widget_unknown_field(kind):
    spec = spec_of(kind)
    spec["sections"][0]["colour"] = 1
    assert artifact_spec.validate(spec) == ["spec:sections[0].colour: unknown field 'colour'"]


def test_layers_duplicate_block_id_across_layers():
    spec = spec_of("layers")
    spec["sections"][0]["layers"][2]["blocks"][0]["id"] = "web"
    assert (
        "spec:sections[0].layers[2].blocks[0].id: duplicate block id 'web'"
        in artifact_spec.validate(spec)
    )


def test_layers_link_to_missing_block():
    assert errors_of("layers", links=[["web", "ghost"]]) == [
        "spec:sections[0].links[0]: link names missing block 'ghost'"
    ]


def test_layers_link_to_itself():
    assert errors_of("layers", links=[["web", "web"]]) == [
        "spec:sections[0].links[0]: link joins a block to itself"
    ]


def test_pivot_default_names_missing_field():
    assert errors_of("pivot", rows="planet") == [
        "spec:sections[0].rows: default 'planet' is not in dims"
    ]


def test_pivot_measure_default_must_be_a_measure():
    assert errors_of("pivot", measure="team") == [
        "spec:sections[0].measure: default 'team' is not in measures"
    ]


def test_pivot_dim_missing_from_records():
    (line,) = errors_of("pivot", dims=["team", "month", "planet"])
    assert line == "spec:sections[0].dims[2]: no record has field 'planet'"


def test_pivot_bad_aggregate():
    (line,) = errors_of("pivot", agg="median")
    assert line.startswith("spec:sections[0].agg: expected one of sum, count")


def test_pivot_measure_must_be_numeric():
    spec = spec_of("pivot")
    spec["sections"][0]["records"][0]["hours"] = "lots"
    assert artifact_spec.validate(spec) == [
        "spec:sections[0].records[0].hours: measure 'hours' is not a number"
    ]


def test_pivot_records_stay_flat():
    spec = spec_of("pivot")
    spec["sections"][0]["records"][0]["extra"] = {"deep": 1}
    assert artifact_spec.validate(spec) == [
        "spec:sections[0].records[0].extra: expected flat text or number"
    ]


def test_treemap_negative_value():
    spec = spec_of("treemap")
    spec["sections"][0]["tree"]["children"][0]["value"] = -5
    assert artifact_spec.validate(spec) == [
        "spec:sections[0].tree.children[0].value: negative value -5"
    ]


def test_treemap_leaf_without_value():
    spec = spec_of("treemap")
    del spec["sections"][0]["tree"]["children"][0]["value"]
    assert artifact_spec.validate(spec) == ["spec:sections[0].tree.children[0]: leaf needs a value"]


def test_treemap_summing_to_zero():
    tree = {"label": "Root", "children": [{"label": "A", "value": 0}]}
    assert errors_of("treemap", tree=tree) == ["spec:sections[0].tree: tree sums to zero"]


def test_sankey_flow_to_missing_node():
    assert errors_of("sankey", flows=[["visit", "ghost", 3]]) == [
        "spec:sections[0].flows[0]: flow names missing node 'ghost'"
    ]


def test_sankey_negative_flow():
    assert errors_of("sankey", flows=[["visit", "sign", -1]]) == [
        "spec:sections[0].flows[0][2]: negative value -1"
    ]


def test_sankey_cycle():
    flows = [["visit", "sign", 1], ["sign", "pay", 1], ["pay", "sign", 1]]
    assert errors_of("sankey", flows=flows) == ["spec:sections[0].flows: cycle through pay, sign"]


def test_sankey_duplicate_node_id():
    spec = spec_of("sankey")
    spec["sections"][0]["nodes"][1]["id"] = "visit"
    (first, *_) = artifact_spec.validate(spec)
    assert first == "spec:sections[0].nodes[1].id: duplicate node id 'visit'"


def test_heatmap_cell_names_missing_row():
    cells = [["Nope", "Sales", 1]]
    assert errors_of("heatmap", cells=cells) == [
        "spec:sections[0].cells[0]: cell names missing row 'Nope'"
    ]


def test_heatmap_duplicate_cell():
    cells = [["Sales", "Cost", 1], ["Sales", "Cost", 2]]
    assert errors_of("heatmap", cells=cells, scale="sequential") == [
        "spec:sections[0].cells[1]: duplicate cell 'Sales' x 'Cost'"
    ]


def test_heatmap_negative_needs_diverging_scale():
    cells = [["Sales", "Cost", -0.4]]
    (line,) = errors_of("heatmap", cells=cells, scale="sequential")
    assert line == (
        "spec:sections[0].cells[0][2]: negative value on a sequential scale; use scale 'diverging'"
    )


def test_heatmap_bad_scale():
    (line,) = errors_of("heatmap", scale="rainbow")
    assert line.startswith("spec:sections[0].scale: expected one of sequential, diverging")


def test_budget_long_lede_warns():
    spec = spec_of("heatmap", lede=" ".join(["word"] * 31))
    spec["sections"].append(BIG)
    assert artifact_budget.warnings(spec) == [
        "text:sections[0].lede: 31 words; move detail into a note or a widget"
    ]


def test_budget_lede_at_limit_is_quiet():
    spec = spec_of("heatmap", lede=" ".join(["w"] * 30))
    spec["sections"].append(BIG)
    assert artifact_budget.warnings(spec) == []


def test_budget_long_paragraph_warns():
    spec = artifact_examples.example("heatmap")
    spec["sections"].append(
        {"type": "prose", "title": "Note", "paragraphs": [" ".join(["w"] * 41)]}
    )
    assert "text:sections[1].paragraphs[0]: 41 words; move detail into a note or a widget" in (
        artifact_budget.warnings(spec)
    )


def test_budget_prose_outweighing_widgets_warns():
    spec = {
        "title": "Page",
        "sections": [
            {"type": "prose", "title": "T", "paragraphs": [" ".join(["w"] * 30)] * 3},
            artifact_examples.SECTIONS["heatmap"],
        ],
    }
    assert artifact_budget.warnings(spec) == [
        "text:$: 90 words; move detail into a note or a widget"
    ]


def test_build_prints_warning_and_still_exits_zero(tmp_path, capsys):
    spec = spec_of("heatmap", lede=" ".join(["word"] * 31))
    src = tmp_path / "p.json"
    src.write_text(json.dumps(spec), encoding="utf-8")
    assert artifact.main(["build", str(src)]) == 0
    assert "text:sections[0].lede: 31 words" in capsys.readouterr().err
    assert (tmp_path / "p.html").exists()


def test_notes_are_tooltips_never_inline_paragraphs():
    kit = Path(artifact.KIT)
    for name in ("board.js", "timeline.js", "graph.js"):
        assert "R.tip(" in (kit / name).read_text(encoding="utf-8"), name
    assert 'class: "note"' not in (kit / "board.js").read_text(encoding="utf-8")


def test_css_defines_both_heat_ramps():
    css = (Path(artifact.KIT) / "kit.css").read_text(encoding="utf-8")
    names = [f"--seq{i}:" for i in range(1, 6)] + [
        f"--div-{n}:" for n in ("n4", "n1", "0", "p1", "p4")
    ]
    for name in names:
        assert css.count(name) == 3, name
