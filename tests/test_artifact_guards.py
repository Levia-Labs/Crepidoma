import artifact_examples
import artifact_spec


def spec_of(kind, **changes):
    spec = artifact_examples.example(kind)
    spec["sections"][0].update(changes)
    return spec


def only_error(spec):
    errors = artifact_spec.validate(spec)
    assert errors and all(e.startswith("spec:") for e in errors)
    return errors


def test_unhashable_values_are_spec_errors_not_crashes():
    only_error(spec_of("layers", links=[[["a"], "b"]]))
    only_error(spec_of("sankey", flows=[[["a"], "b", 1]]))
    only_error(spec_of("heatmap", cells=[[["a"], {"b": 1}, 1]]))
    only_error(spec_of("pivot", measures=[["hours"]]))
    only_error(spec_of("pivot", measure=["hours"]))
    only_error(spec_of("pivot", rows=["team"]))


def test_unhashable_values_in_shared_shapes_are_spec_errors():
    for change in ({"edges": [["n", ["x"]]]}, {"start": ["x"]}):
        only_error(spec_of("graph", **change))
    for tone in (["info"], {"a": 1}):
        spec = artifact_examples.example("cards")
        spec["sections"][0]["items"][0]["tone"] = tone
        only_error(spec)


def test_board_status_unhashable_is_spec_error():
    spec = artifact_examples.example("board")
    spec["sections"][0]["bands"][0]["groups"][0]["items"][0]["status"] = ["x"]
    only_error(spec)


def test_pivot_record_must_carry_the_measure():
    spec = spec_of("pivot")
    del spec["sections"][0]["records"][0]["hours"]
    assert artifact_spec.validate(spec) == [
        "spec:sections[0].records[0].hours: record lacks measure 'hours'"
    ]


def test_sankey_flow_must_advance_stage():
    spec = spec_of("sankey")
    nodes = spec["sections"][0]["nodes"]
    nodes[0]["stage"], nodes[1]["stage"] = 2, 1
    spec["sections"][0]["flows"] = [[nodes[0]["id"], nodes[1]["id"], 1]]
    (line,) = artifact_spec.validate(spec)
    assert line.startswith("spec:sections[0].flows[0]: flow does not advance stage")
