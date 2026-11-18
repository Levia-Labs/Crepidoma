"""Shapes and cross-checks of the correlation widgets: layers, pivot, treemap, sankey, heatmap."""

from __future__ import annotations

from artifact_shapes import cycle_nodes
from artifact_spec import Checker, as_list, is_int

AGGREGATES = ("sum", "count", "avg", "min", "max")
SCALES = ("sequential", "diverging")


def is_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def shape(c: Checker, fields: dict, required: tuple = ()):
    return lambda v, p: c.obj(v, p, fields, required)


def number(c: Checker, nonnegative: bool = False):
    def check(value: object, path: str) -> None:
        if not is_number(value):
            c.err(path, "expected a number")
        elif nonnegative and value < 0:
            c.err(path, f"negative value {value}")

    return check


def tuple_of(c: Checker, kinds: tuple, nonnegative: bool = False):
    """A fixed-length list: each kind is 'text' or 'number'."""

    def check(value: object, path: str) -> None:
        if not isinstance(value, list) or len(value) != len(kinds):
            c.err(path, f"expected a list of {len(kinds)}: {', '.join(kinds)}")
            return
        for index, kind in enumerate(kinds):
            where = f"{path}[{index}]"
            if kind == "text":
                c.text(value[index], where)
            else:
                number(c, nonnegative)(value[index], where)

    return check


def shapes_layers(c: Checker):
    block = shape(
        c,
        {"id": c.text, "label": c.text, "note": c.text, "tone": c.tone},
        ("id", "label"),
    )
    layer = shape(
        c,
        {"id": c.text, "label": c.text, "blocks": c.many(block, 1)},
        ("id", "label", "blocks"),
    )
    fields = {
        "title": c.text,
        "lede": c.text,
        "layers": c.many(layer, 1),
        "links": c.many(tuple_of(c, ("text", "text"))),
    }
    return fields, ("title", "layers")


def shapes_pivot(c: Checker):
    fields = {
        "title": c.text,
        "lede": c.text,
        "records": c.many(lambda v, p: None, 1),
        "dims": c.many(c.text, 1),
        "measures": c.many(c.text, 1),
        "rows": c.text,
        "cols": c.text,
        "measure": c.text,
        "agg": lambda v, p: v in AGGREGATES or c.err(p, f"expected one of {', '.join(AGGREGATES)}"),
    }
    return fields, ("title", "records", "dims", "measures")


def shapes_treemap(c: Checker):
    def node(value: object, path: str) -> None:
        fields = {
            "label": c.text,
            "value": number(c, True),
            "tone": c.tone,
            "note": c.text,
            "children": c.many(node),
        }
        c.obj(value, path, fields, ("label",))
        if isinstance(value, dict) and not value.get("children") and "value" not in value:
            c.err(path, "leaf needs a value")

    return {"title": c.text, "lede": c.text, "tree": node}, ("title", "tree")


def shapes_sankey(c: Checker):
    node = shape(c, {"id": c.text, "label": c.text, "stage": c.integer(0)}, ("id", "label"))
    fields = {
        "title": c.text,
        "lede": c.text,
        "nodes": c.many(node, 2),
        "flows": c.many(tuple_of(c, ("text", "text", "number"), True), 1),
    }
    return fields, ("title", "nodes", "flows")


def shapes_heatmap(c: Checker):
    fields = {
        "title": c.text,
        "lede": c.text,
        "rows": c.many(c.text, 1),
        "cols": c.many(c.text, 1),
        "cells": c.many(tuple_of(c, ("text", "text", "number")), 1),
        "scale": lambda v, p: v in SCALES or c.err(p, f"expected one of {', '.join(SCALES)}"),
    }
    return fields, ("title", "rows", "cols", "cells")


def layers_refs(c: Checker, value: dict, path: str) -> None:
    layers = as_list(value.get("layers"))
    c.unique(layers, "id", f"{path}.layers", "layer")
    ids: set[str] = set()
    for li, layer in enumerate(layers):
        for bi, block in enumerate(
            as_list(layer.get("blocks") if isinstance(layer, dict) else None)
        ):
            ident = block.get("id") if isinstance(block, dict) else None
            if isinstance(ident, str) and ident in ids:
                c.err(f"{path}.layers[{li}].blocks[{bi}].id", f"duplicate block id '{ident}'")
            if isinstance(ident, str):
                ids.add(ident)
    for index, link in enumerate(as_list(value.get("links"))):
        if not (isinstance(link, list) and len(link) == 2):
            continue
        where = f"{path}.links[{index}]"
        missing = [n for n in link if not isinstance(n, str) or n not in ids]
        for name in missing:
            c.err(where, f"link names missing block '{name}'")
        if not missing and link[0] == link[1]:
            c.err(where, "link joins a block to itself")


def pivot_refs(c: Checker, value: dict, path: str) -> None:
    records = [r for r in as_list(value.get("records")) if isinstance(r, dict)]
    fields: set[str] = set()
    for index, record in enumerate(as_list(value.get("records"))):
        if not isinstance(record, dict):
            c.err(f"{path}.records[{index}]", "expected an object")
            continue
        fields |= set(record)
        for key, item in record.items():
            if not isinstance(item, str | int | float):
                c.err(f"{path}.records[{index}].{key}", "expected flat text or number")
    for key in ("dims", "measures"):
        for index, name in enumerate(as_list(value.get(key))):
            if isinstance(name, str) and name not in fields:
                c.err(f"{path}.{key}[{index}]", f"no record has field '{name}'")
    measures = as_list(value.get("measures"))
    for name in measures:
        if not isinstance(name, str):
            continue
        for index, record in enumerate(records):
            if name not in record:
                c.err(f"{path}.records[{index}].{name}", f"record lacks measure '{name}'")
            elif not is_number(record[name]):
                c.err(f"{path}.records[{index}].{name}", f"measure '{name}' is not a number")
    for key, pool in (("rows", "dims"), ("cols", "dims"), ("measure", "measures")):
        if key in value and value[key] not in as_list(value.get(pool)):
            c.err(f"{path}.{key}", f"default '{value[key]}' is not in {pool}")


def tree_total(node: object) -> float:
    if not isinstance(node, dict):
        return 0
    kids = as_list(node.get("children"))
    if kids:
        return sum(tree_total(k) for k in kids)
    value = node.get("value")
    return value if is_number(value) else 0


def treemap_refs(c: Checker, value: dict, path: str) -> None:
    if isinstance(value.get("tree"), dict) and tree_total(value["tree"]) <= 0:
        c.err(f"{path}.tree", "tree sums to zero")


def sankey_refs(c: Checker, value: dict, path: str) -> None:
    ids = c.unique(value.get("nodes"), "id", f"{path}.nodes", "node")
    edges: dict[str, list[str]] = {i: [] for i in ids}
    stages = {
        n["id"]: n.get("stage")
        for n in as_list(value.get("nodes"))
        if isinstance(n, dict) and isinstance(n.get("id"), str)
    }
    for index, flow in enumerate(as_list(value.get("flows"))):
        if not (isinstance(flow, list) and len(flow) == 3):
            continue
        where = f"{path}.flows[{index}]"
        missing = [n for n in flow[:2] if not isinstance(n, str) or n not in ids]
        for name in missing:
            c.err(where, f"flow names missing node '{name}'")
        if not missing:
            edges[flow[0]].append(flow[1])
            a, b = stages.get(flow[0]), stages.get(flow[1])
            if is_int(a) and is_int(b) and b <= a:
                c.err(where, f"flow does not advance stage ({flow[0]} {a} to {flow[1]} {b})")
    stuck = cycle_nodes(edges)
    if stuck:
        c.err(f"{path}.flows", f"cycle through {', '.join(sorted(stuck))}")


def heatmap_refs(c: Checker, value: dict, path: str) -> None:
    rows, cols = as_list(value.get("rows")), as_list(value.get("cols"))
    for key, names in (("rows", rows), ("cols", cols)):
        for index in range(len(names)):
            if names[index] in names[:index]:
                c.err(f"{path}.{key}[{index}]", f"duplicate {key[:-1]} '{names[index]}'")
    seen: set[tuple] = set()
    for index, cell in enumerate(as_list(value.get("cells"))):
        if not (isinstance(cell, list) and len(cell) == 3):
            continue
        where = f"{path}.cells[{index}]"
        if cell[0] not in rows:
            c.err(where, f"cell names missing row '{cell[0]}'")
        if cell[1] not in cols:
            c.err(where, f"cell names missing column '{cell[1]}'")
        if not (isinstance(cell[0], str) and isinstance(cell[1], str)):
            continue
        if (cell[0], cell[1]) in seen:
            c.err(where, f"duplicate cell '{cell[0]}' x '{cell[1]}'")
        seen.add((cell[0], cell[1]))
        if is_number(cell[2]) and cell[2] < 0 and value.get("scale", "sequential") == "sequential":
            c.err(f"{where}[2]", "negative value on a sequential scale; use scale 'diverging'")


WIDGET_SHAPES = {
    "layers": shapes_layers,
    "pivot": shapes_pivot,
    "treemap": shapes_treemap,
    "sankey": shapes_sankey,
    "heatmap": shapes_heatmap,
}
WIDGET_REFS = {
    "layers": layers_refs,
    "pivot": pivot_refs,
    "treemap": treemap_refs,
    "sankey": sankey_refs,
    "heatmap": heatmap_refs,
}
