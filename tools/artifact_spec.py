"""Validation of an artifact page spec; see artifact_kit/SPEC.md for the schema.

Every problem is one line `spec:<json path>: message`, so a caller can print them as they are.
"""

from __future__ import annotations

import json
import re
from functools import cache
from pathlib import Path

TONES = {"out", "new", "keep", "wait", "bad", "neutral"} | {f"c{i}" for i in range(1, 9)}
SECTION_ID = re.compile(r"^[A-Za-z0-9-]+$")
TITLE_EXPLAINER = re.compile(r"\s[-\u2013\u2014]\s|[\u2013\u2014:]")
MAX_TITLE_WORDS = 4


@cache
def ui_dictionary() -> dict:
    """Interface words per language, shared by the validator and the page script."""
    path = Path(__file__).resolve().parent / "artifact_kit" / "ui.json"
    return json.loads(path.read_text(encoding="utf-8"))


def is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def as_list(value: object) -> list:
    return value if isinstance(value, list) else []


class Checker:
    """Collects errors while walking the spec."""

    def __init__(self) -> None:
        self.errors: list[str] = []

    def err(self, path: str, message: str) -> None:
        self.errors.append(f"spec:{path}: {message}")

    def obj(self, value: object, path: str, fields: dict, required: tuple = ()) -> dict | None:
        """Check an object against {field: checker(value, path)}; unknown fields are errors."""
        if not isinstance(value, dict):
            self.err(path, "expected an object")
            return None
        for key, item in value.items():
            if key not in fields:
                self.err(f"{path}.{key}", f"unknown field '{key}'")
            else:
                fields[key](item, f"{path}.{key}")
        for key in required:
            if key not in value:
                self.err(f"{path}.{key}", f"missing field '{key}'")
        return value

    def maybe(self, value: object, path: str) -> None:
        """Text that may be empty; an empty value is dropped from the page."""
        if not isinstance(value, str):
            self.err(path, "expected text")

    def text(self, value: object, path: str) -> None:
        if not isinstance(value, str) or not value.strip():
            self.err(path, "expected non-empty text")

    def integer(self, minimum: int):
        def check(value: object, path: str) -> None:
            if not is_int(value) or value < minimum:
                self.err(path, f"expected an integer of at least {minimum}")

        return check

    def tone(self, value: object, path: str) -> None:
        if not isinstance(value, str) or value not in TONES:
            self.err(path, f"bad tone '{value}'; use one of {', '.join(sorted(TONES))}")

    def many(self, item, minimum: int = 0):
        def check(value: object, path: str) -> None:
            if not isinstance(value, list):
                self.err(path, "expected a list")
                return
            if len(value) < minimum:
                self.err(path, f"expected at least {minimum} item(s)")
            for index, entry in enumerate(value):
                item(entry, f"{path}[{index}]")

        return check

    def unique(self, entries: object, key: str, path: str, what: str) -> set[str]:
        """Ids seen in a list of objects; report each repeat."""
        seen: set[str] = set()
        if not isinstance(entries, list):
            return seen
        for index, entry in enumerate(entries):
            ident = entry.get(key) if isinstance(entry, dict) else None
            if not isinstance(ident, str):
                continue
            if ident in seen:
                self.err(f"{path}[{index}].{key}", f"duplicate {what} id '{ident}'")
            seen.add(ident)
        return seen

    def check_title(self, value: object) -> None:
        self.text(value, "title")
        if not isinstance(value, str):
            return
        if len(value.split()) > MAX_TITLE_WORDS:
            self.err("title", f"title is over {MAX_TITLE_WORDS} words")
        if TITLE_EXPLAINER.search(value):
            self.err("title", "title carries an explainer after a dash or colon")


def validate(spec: object) -> list[str]:
    """Return every spec error as a `spec:<path>: message` line; empty when the spec is sound."""
    c = Checker()
    t, many, obj = c.text, c.many, c.obj
    sections = spec.get("sections") if isinstance(spec, dict) else None
    ids = c.unique(sections, "id", "sections", "section")
    top = {
        "title": lambda v, p: c.check_title(v),
        "lang": t,
        "ui": lambda v, p: obj(v, p, dict.fromkeys(ui_dictionary()["en"], t)),
        "eyebrow": t,
        "lede": t,
        "stats": many(lambda v, p: obj(v, p, {"value": t, "label": t}, ("value", "label"))),
        "sections": many(lambda v, p: section(c, v, p, ids)),
    }
    obj(spec, "", top, ("title", "sections"))
    return [line.replace("spec:.", "spec:", 1).replace("spec::", "spec:$:", 1) for line in c.errors]


def section(c: Checker, value: object, path: str, section_ids: set[str]) -> None:
    from artifact_shapes import SECTION_SHAPES, check_graph
    from artifact_widgets import WIDGET_REFS, WIDGET_SHAPES

    if not isinstance(value, dict):
        c.err(path, "expected an object")
        return
    kind = value.get("type")
    shapes = {**SECTION_SHAPES, **WIDGET_SHAPES}
    if kind not in shapes:
        c.err(f"{path}.type", f"unknown section type '{kind}'")
        return
    fields, required = shapes[kind](c)
    fields = {"type": lambda v, p: None, "id": lambda v, p: section_id(c, v, p), **fields}
    c.obj(value, path, fields, ("type", *required))
    if kind == "graph":
        check_graph(c, value, path)
    elif kind == "board":
        board_refs(c, value, path)
    elif kind == "timeline":
        timeline_refs(c, value, path, section_ids)
    elif kind in WIDGET_REFS:
        WIDGET_REFS[kind](c, value, path)


def section_id(c: Checker, value: object, path: str) -> None:
    if not isinstance(value, str) or not SECTION_ID.match(value):
        c.err(path, "expected letters, digits and '-' only")


def board_refs(c: Checker, value: dict, path: str) -> None:
    statuses = c.unique(value.get("statuses"), "id", f"{path}.statuses", "status")
    items: list[tuple[str, dict]] = []
    for bi, band in enumerate(as_list(value.get("bands"))):
        for gi, group in enumerate(as_list(band.get("groups") if isinstance(band, dict) else None)):
            for ii, item in enumerate(
                as_list(group.get("items") if isinstance(group, dict) else None)
            ):
                items.append((f"{path}.bands[{bi}].groups[{gi}].items[{ii}]", item))
    seen: set[str] = set()
    for where, item in items:
        if not isinstance(item, dict):
            continue
        if isinstance(item.get("id"), str):
            if item["id"] in seen:
                c.err(f"{where}.id", f"duplicate item id '{item['id']}'")
            seen.add(item["id"])
        status = item.get("status")
        if "status" in item and not (isinstance(status, str) and status in statuses):
            c.err(f"{where}.status", f"unknown status '{item['status']}'")


def timeline_refs(c: Checker, value: dict, path: str, section_ids: set[str]) -> None:
    units = value.get("units")
    count = len(units) if isinstance(units, list) else 0
    for index, row in enumerate(as_list(value.get("rows"))):
        if not isinstance(row, dict):
            continue
        where = f"{path}.rows[{index}]"
        start, span = row.get("start"), row.get("span")
        if is_int(start) and is_int(span) and span >= 1 and start >= 0 and start + span > count:
            c.err(where, f"bar ends at unit {start + span}, past the {count} units")
        if "target" in row and row["target"] not in section_ids:
            c.err(f"{where}.target", f"unknown section id '{row['target']}'")
