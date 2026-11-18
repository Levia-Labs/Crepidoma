"""Small working example specs, one per kind, for `artifact.py new`."""

from __future__ import annotations

import copy

TITLE = {"title": "Sample page", "lang": "en", "lede": "Replace this lede."}

GRAPH = {
    "type": "graph",
    "title": "Dependencies",
    "categories": [{"id": "a", "label": "Planning"}, {"id": "b", "label": "Doing"}],
    "nodes": [
        {"id": "plan", "label": "Plan", "category": "a", "note": "Where it starts."},
        {"id": "build", "label": "Build", "category": "b"},
        {"id": "ship", "label": "Ship", "category": "b", "flag": "fix"},
    ],
    "edges": [["plan", "build"], ["build", "ship"]],
    "start": "plan",
}

BOARD = {
    "type": "board",
    "title": "Status",
    "statuses": [
        {"id": "done", "label": "Done", "tone": "keep"},
        {"id": "next", "label": "Next", "tone": "new"},
    ],
    "bands": [
        {
            "tone": "keep",
            "title": "Finished",
            "groups": [{"title": "Group", "items": [{"title": "First item", "status": "done"}]}],
        },
        {
            "tone": "new",
            "title": "Coming",
            "groups": [{"title": "Group", "items": [{"title": "Second item", "status": "next"}]}],
        },
    ],
}

TIMELINE = {
    "type": "timeline",
    "title": "Schedule",
    "units": ["W1", "W2", "W3", "W4"],
    "rows": [
        {"label": "Design", "start": 0, "span": 2, "tone": "c3"},
        {"label": "Build", "start": 2, "span": 2, "tone": "new", "note": "After design"},
    ],
}

CARDS = {
    "type": "cards",
    "title": "Options",
    "items": [
        {
            "title": "First",
            "body": "One sentence with **bold** and `code`.",
            "tag": "new",
            "tone": "new",
        },
        {"title": "Second", "body": "Another sentence.", "tone": "keep"},
    ],
}

LAYERS = {
    "type": "layers",
    "title": "Layers",
    "layers": [
        {
            "id": "top",
            "label": "Apps",
            "blocks": [{"id": "web", "label": "Web", "note": "Calls the services."}],
        },
        {
            "id": "mid",
            "label": "Services",
            "blocks": [
                {"id": "api", "label": "API", "tone": "new"},
                {"id": "jobs", "label": "Jobs", "tone": "new"},
            ],
        },
        {
            "id": "low",
            "label": "Data",
            "blocks": [{"id": "db", "label": "Database", "tone": "keep"}],
        },
    ],
    "links": [["web", "api"], ["api", "db"], ["jobs", "db"]],
}

PIVOT = {
    "type": "pivot",
    "title": "Pivot",
    "records": [
        {"team": "A", "month": "Jan", "hours": 12},
        {"team": "A", "month": "Feb", "hours": 8},
        {"team": "B", "month": "Jan", "hours": 5},
        {"team": "B", "month": "Feb", "hours": 14},
    ],
    "dims": ["team", "month"],
    "measures": ["hours"],
    "rows": "team",
    "cols": "month",
    "measure": "hours",
    "agg": "sum",
}

TREEMAP = {
    "type": "treemap",
    "title": "Treemap",
    "tree": {
        "label": "Budget",
        "children": [
            {"label": "People", "value": 60, "note": "Salaries."},
            {
                "label": "Tools",
                "children": [{"label": "Cloud", "value": 25}, {"label": "Licences", "value": 15}],
            },
        ],
    },
}

SANKEY = {
    "type": "sankey",
    "title": "Flow",
    "nodes": [
        {"id": "visit", "label": "Visits"},
        {"id": "sign", "label": "Sign-ups"},
        {"id": "bounce", "label": "Left"},
        {"id": "pay", "label": "Paying"},
    ],
    "flows": [
        ["visit", "sign", 30],
        ["visit", "bounce", 70],
        ["sign", "pay", 12],
        ["sign", "bounce", 18],
    ],
}

HEATMAP = {
    "type": "heatmap",
    "title": "Correlation",
    "scale": "diverging",
    "rows": ["Sales", "Cost"],
    "cols": ["Sales", "Cost"],
    "cells": [
        ["Sales", "Sales", 1],
        ["Sales", "Cost", -0.4],
        ["Cost", "Sales", -0.4],
        ["Cost", "Cost", 1],
    ],
}

SECTIONS = {
    "graph": GRAPH,
    "board": BOARD,
    "timeline": TIMELINE,
    "cards": CARDS,
    "layers": LAYERS,
    "pivot": PIVOT,
    "treemap": TREEMAP,
    "sankey": SANKEY,
    "heatmap": HEATMAP,
}


def example(kind: str) -> dict:
    """A complete spec holding one section of the given kind."""
    return copy.deepcopy({**TITLE, "sections": [SECTIONS[kind]]})
