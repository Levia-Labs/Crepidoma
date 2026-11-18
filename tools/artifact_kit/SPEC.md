# Artifact spec

A page is one JSON file. Every text field is plain text; `**bold**`, `` `code` `` and `[label](https://url)` are the only inline marks (a link opens in a new tab; any other scheme stays plain text). `artifact.py build` escapes the rest.

```json
{
  "title": "Graf zależności projektu",
  "lang": "pl",
  "eyebrow": "Projekt · przebudowa",
  "lede": "One paragraph under the title.",
  "stats": [{ "value": "21", "label": "systemów" }],
  "sections": []
}
```

`title` is the artifact's name: two to four words, no explainer after a dash or colon.

## Section types

| `type`     | Fields                                                                                                                                    | Renders                                                                                                                                          |
| ---------- | ----------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `prose`    | `title`, `paragraphs[]`                                                                                                                   | Text block, 68ch wide                                                                                                                            |
| `cards`    | `title`, `lede`, `items[{title, body, tag?, tone?}]`                                                                                      | Card grid                                                                                                                                        |
| `board`    | `title`, `lede`, `statuses[{id, label, tone}]`, `bands[{tone, title, lede, groups[{title, note, items[{id?, title, note?, status?}]}]}]`  | Coloured bands of grouped items with status chips                                                                                                |
| `timeline` | `title`, `lede`, `units[]`, `rows[{label, start, span, tone, note?, target?}]`                                                            | Waterfall bars over unit columns; `start` is a 0-based unit index, `start + span` stays within `units`; `target` names a section id to scroll to |
| `graph`    | `title`, `lede`, `categories[{id, label}]`, `columns[]?`, `lanes[]?`, `nodes[]`, `edges[[from, to]]`, `start?`, `mode?`                   | Interactive dependency graph with a detail panel                                                                                                 |
| `layers`   | `title`, `lede`, `layers[{id, label, blocks[{id, label, note?, tone?}]}]`, `links[[from, to]]`                                            | Stacked layers; selecting a block lights its links across layers, detail strip shows note and linked labels                                      |
| `pivot`    | `title`, `lede`, `records[{flat fields}]`, `dims[]`, `measures[]`, `rows?`, `cols?`, `measure?`, `agg?` (`sum` `count` `avg` `min` `max`) | Row, column, measure and aggregation selects; heat-shaded cells, totals; a click lists the matching records                                      |
| `treemap`  | `title`, `lede`, `tree{label, value?, tone?, note?, children[]}`                                                                          | Squarified blocks, values summed upward; click zooms, breadcrumb climbs back; hover shows value and share                                        |
| `sankey`   | `title`, `lede`, `nodes[{id, label, stage?}]`, `flows[[from, to, value]]`                                                                 | Stage columns, node height by throughput; hover a node or flow lights its connected paths                                                        |
| `heatmap`  | `title`, `lede`, `rows[]`, `cols[]`, `cells[[row, col, value]]`, `scale?` (`sequential` `diverging`)                                      | Shaded grid; crosshair on hover, value in a detail strip, legend bar; `diverging` is centred at 0                                                |

Every section takes an optional `id` (anchor, letters, digits, `-`).

## Pick the widget

| Question                        | Section    |
| ------------------------------- | ---------- |
| Dependency or order             | `graph`    |
| Ownership or stacking           | `layers`   |
| Part of a whole, size           | `treemap`  |
| Volume moving between stages    | `sankey`   |
| Two-way comparison of records   | `pivot`    |
| Strength of a pairwise relation | `heatmap`  |
| Schedule                        | `timeline` |
| State of many items             | `board`    |

## Language

- `lang` picks the interface words the renderers print (Requires, Rows, Total and the like): `en` and `pl` are built in, any other value falls back to `en`.
- `ui` is an optional object of overrides; its keys must exist in [`ui.json`](ui.json). Templates use `{name}` slots.
- On a board, `band.lede`, `group.note` and item `note` may be empty; empty text is left out of the page.

## Widgets

- Defaults select something on load, so every widget is complete at rest: the strongest cell, the first linked block, the biggest node.
- Hover, focus and tap do the same thing; every target is keyboard reachable.
- Layers: block ids are unique across all layers; a link joins two different blocks.
- Pivot: `rows`, `cols` default to the first dims, `measure` to the first measure, `agg` to `sum`; measure fields must be numbers.
- Treemap: every leaf has a non-negative `value`, and the tree sums above zero.
- Sankey: flows are non-negative and must not form a cycle; `stage` defaults to the longest-path depth.
- Heatmap: a sequential scale takes no negative values; one cell per row and column pair.
- Every `note` shows on hover, focus or tap, never inline. Text budget: a lede over 30 words, a prose paragraph over 40, or prose words above 3 per widget element each print a `text:<path>: N words; move detail into a note or a widget` warning from `build` (exit stays 0).

## Graph

- Node: `{id, label, category, column?, lane?, note?, flag?, facts?: [{label, items[]}]}`.
- Edge `[a, b]`: `a` is a prerequisite of `b`. Edges must form a DAG over existing node ids.
- `column` defaults to the node's longest-path depth; `columns[]` names the column headers. `lanes[]` names horizontal lanes; a node's `lane` is an index into it.
- `flag: "fix"` marks a node that needs a fix.
- `mode`: `direct` (default) highlights direct prerequisites and dependents, `chain` the full upstream and downstream closure. The page has a toggle.
- `start`: node selected on load, so the page is complete at rest.

## Tones

`categories` take series colours `c1`..`c8` in order. Bands, cards, rows and statuses take a `tone`: `out`, `new`, `keep`, `wait`, `bad`, `neutral`, or a series colour.
