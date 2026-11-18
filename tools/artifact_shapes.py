"""Field shapes of each artifact section type, and the whole-graph checks."""

from __future__ import annotations

from artifact_spec import Checker, is_int


def shapes_prose(c: Checker):
    return {"title": c.text, "paragraphs": c.many(c.text, 1)}, ("title", "paragraphs")


def shapes_cards(c: Checker):
    card = lambda v, p: c.obj(  # noqa: E731
        v,
        p,
        {"title": c.text, "body": c.text, "tag": c.text, "tone": c.tone},
        ("title",),
    )
    return {"title": c.text, "lede": c.text, "items": c.many(card, 1)}, ("title", "items")


def shapes_board(c: Checker):
    status = lambda v, p: c.obj(  # noqa: E731
        v, p, {"id": c.text, "label": c.text, "tone": c.tone}, ("id", "label", "tone")
    )
    item = lambda v, p: c.obj(  # noqa: E731
        v, p, {"id": c.text, "title": c.text, "note": c.maybe, "status": c.text}, ("title",)
    )
    group = lambda v, p: c.obj(  # noqa: E731
        v, p, {"title": c.text, "note": c.maybe, "items": c.many(item)}, ("title", "items")
    )
    band = lambda v, p: c.obj(  # noqa: E731
        v,
        p,
        {"tone": c.tone, "title": c.text, "lede": c.maybe, "groups": c.many(group)},
        ("tone", "title", "groups"),
    )
    fields = {
        "title": c.text,
        "lede": c.text,
        "statuses": c.many(status),
        "bands": c.many(band, 1),
    }
    return fields, ("title", "bands")


def shapes_timeline(c: Checker):
    row = lambda v, p: c.obj(  # noqa: E731
        v,
        p,
        {
            "label": c.text,
            "start": c.integer(0),
            "span": c.integer(1),
            "tone": c.tone,
            "note": c.text,
            "target": c.text,
        },
        ("label", "start", "span", "tone"),
    )
    fields = {"title": c.text, "lede": c.text, "units": c.many(c.text, 1), "rows": c.many(row, 1)}
    return fields, ("title", "units", "rows")


def shapes_graph(c: Checker):
    category = lambda v, p: c.obj(v, p, {"id": c.text, "label": c.text}, ("id", "label"))  # noqa: E731
    fact = lambda v, p: c.obj(  # noqa: E731
        v, p, {"label": c.text, "items": c.many(c.text)}, ("label", "items")
    )
    node = lambda v, p: c.obj(  # noqa: E731
        v,
        p,
        {
            "id": c.text,
            "label": c.text,
            "category": c.text,
            "column": c.integer(0),
            "lane": c.integer(0),
            "note": c.text,
            "flag": lambda x, q: x == "fix" or c.err(q, "expected 'fix'"),
            "facts": c.many(fact),
        },
        ("id", "label", "category"),
    )
    fields = {
        "title": c.text,
        "lede": c.text,
        "categories": c.many(category, 1),
        "columns": c.many(c.text),
        "lanes": c.many(c.text),
        "nodes": c.many(node, 1),
        "edges": c.many(lambda v, p: c.many(c.text)(v, p)),
        "start": c.text,
        "mode": lambda x, q: x in ("direct", "chain") or c.err(q, "expected 'direct' or 'chain'"),
    }
    return fields, ("title", "categories", "nodes")


SECTION_SHAPES = {
    "prose": shapes_prose,
    "cards": shapes_cards,
    "board": shapes_board,
    "timeline": shapes_timeline,
    "graph": shapes_graph,
}


def check_graph(c: Checker, graph: dict, path: str) -> None:
    """Cross-checks: duplicate ids, categories, lanes, edges to missing nodes, start, cycles."""
    nodes = graph.get("nodes") if isinstance(graph.get("nodes"), list) else []
    ids = c.unique(nodes, "id", f"{path}.nodes", "node")
    categories = c.unique(graph.get("categories"), "id", f"{path}.categories", "category")
    lanes = graph.get("lanes")
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            continue
        where = f"{path}.nodes[{index}]"
        if isinstance(node.get("category"), str) and node["category"] not in categories:
            c.err(f"{where}.category", f"unknown category '{node['category']}'")
        if is_int(node.get("lane")) and not (isinstance(lanes, list) and node["lane"] < len(lanes)):
            c.err(f"{where}.lane", "lane index outside lanes")
    graph_edges: dict[str, list[str]] = {i: [] for i in ids}
    edges = graph.get("edges") if isinstance(graph.get("edges"), list) else []
    for index, edge in enumerate(edges):
        where = f"{path}.edges[{index}]"
        if not isinstance(edge, list) or len(edge) != 2:
            c.err(where, "expected [from, to]")
            continue
        missing = [n for n in edge if not isinstance(n, str) or n not in ids]
        for name in missing:
            c.err(where, f"edge names missing node '{name}'")
        if not missing:
            graph_edges[edge[0]].append(edge[1])
    if "start" in graph and not (isinstance(graph["start"], str) and graph["start"] in ids):
        c.err(f"{path}.start", f"start names missing node '{graph['start']}'")
    stuck = cycle_nodes(graph_edges)
    if stuck:
        c.err(f"{path}.edges", f"cycle through {', '.join(sorted(stuck))}")


def cycle_nodes(edges: dict[str, list[str]]) -> set[str]:
    """Nodes left after peeling those with no unresolved prerequisite (Kahn); empty for a DAG."""
    indegree = {n: 0 for n in edges}
    for targets in edges.values():
        for target in targets:
            indegree[target] += 1
    ready = [n for n, d in indegree.items() if d == 0]
    while ready:
        node = ready.pop()
        indegree.pop(node)
        for target in edges[node]:
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
    return set(indegree)
