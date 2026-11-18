"""Text budget of an artifact page: warnings when prose outweighs the widgets.

A warning is one line `text:<json path>: N words; move detail into a note or a widget`.
"""

from __future__ import annotations

MAX_LEDE = 30
MAX_PARAGRAPH = 40
MAX_RATIO = 3


def words(text: object) -> int:
    return len(text.split()) if isinstance(text, str) else 0


def tree_nodes(node: object) -> int:
    if not isinstance(node, dict):
        return 0
    return 1 + sum(tree_nodes(k) for k in node.get("children", []))


def elements(section: dict) -> int:
    """Widget elements in a section: nodes, blocks, records, cells, items, rows, flows."""
    kind = section.get("type")
    if kind == "board":
        groups = [g for b in section.get("bands", []) for g in b.get("groups", [])]
        return sum(len(g.get("items", [])) for g in groups)
    if kind == "layers":
        return sum(len(layer.get("blocks", [])) for layer in section.get("layers", []))
    if kind == "treemap":
        return tree_nodes(section.get("tree"))
    keys = {
        "cards": "items",
        "timeline": "rows",
        "graph": "nodes",
        "pivot": "records",
        "sankey": "nodes",
        "heatmap": "cells",
    }
    return len(section.get(keys.get(kind, ""), []))


def warnings(spec: dict) -> list[str]:
    """Budget warnings for a spec that already passed validation."""
    out: list[str] = []

    def warn(path: str, count: int) -> None:
        out.append(f"text:{path}: {count} words; move detail into a note or a widget")

    prose = 0
    if words(spec.get("lede")) > MAX_LEDE:
        warn("lede", words(spec["lede"]))
    prose += words(spec.get("lede"))
    for index, section in enumerate(spec["sections"]):
        base = f"sections[{index}]"
        if words(section.get("lede")) > MAX_LEDE:
            warn(f"{base}.lede", words(section["lede"]))
        prose += words(section.get("lede"))
        for pi, paragraph in enumerate(section.get("paragraphs", [])):
            if words(paragraph) > MAX_PARAGRAPH:
                warn(f"{base}.paragraphs[{pi}]", words(paragraph))
            prose += words(paragraph)
    total = sum(elements(s) for s in spec["sections"])
    if prose > MAX_RATIO * total:
        warn("$", prose)
    return out
