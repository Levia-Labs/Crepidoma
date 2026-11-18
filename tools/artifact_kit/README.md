# Artifact kit

- Stylesheet and scripts that [`artifact.py`](../artifact.py) inlines into one self-contained claude.ai artifact page: planning boards, dependency graphs and timelines. Spec schema: [SPEC.md](SPEC.md).
- One look: Archivo headings, IBM Plex Sans body, IBM Plex Mono data, cool paper neutrals, light and dark from one token set.
- [`core.js`](core.js) is always included; each section renderer only when the spec uses its type.

## Contents

<!-- contents:start -->

- [`SPEC.md`](SPEC.md) - JSON spec schema: page fields, section types, graph rules, tones.
- [`board.js`](board.js) - Board renderer: tone bands of grouped items with status chips.
- [`cards.js`](cards.js) - Card grid renderer.
- [`core.js`](core.js) - DOM helpers, inline marks, page header, section dispatch.
- [`example.json`](example.json) - Demo spec with a graph, a board and a timeline.
- [`gallery.json`](gallery.json) - Gallery spec using every section type, for a quick visual check.
- [`graph.js`](graph.js) - Dependency graph renderer: SVG nodes and edges, selection walk, detail panel.
- [`heatmap.js`](heatmap.js) - Heatmap renderer: sequential or diverging grid with crosshair and legend.
- [`kit.css`](kit.css) - Theme tokens for light and dark, typography and components.
- [`layers.js`](layers.js) - Layers renderer: stacked blocks with links lit on selection.
- [`pivot.js`](pivot.js) - Pivot renderer: record table with swappable dimensions, measure and aggregate.
- [`prose.js`](prose.js) - Prose section renderer.
- [`sankey.js`](sankey.js) - Sankey renderer: staged nodes and flow bands lit on hover.
- [`timeline.js`](timeline.js) - Waterfall timeline renderer.
- [`treemap.js`](treemap.js) - Treemap renderer: squarified blocks with zoom and breadcrumb.
- [`ui.json`](ui.json) - Interface words per language (en, pl) shared by the validator and the page script.

<!-- contents:end -->
