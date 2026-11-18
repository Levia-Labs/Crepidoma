---
name: artifact-pages
description: Use when making or updating a claude.ai artifact page that explains a system, plan or data to a team - dependency graph, layer map, treemap, sankey, pivot table, heatmap, timeline, status board - so it is built widget-first from a JSON spec with the shared artifact kit and passes the publish contract lint.
---

# Artifact pages

The spec is the source; the page is a build output. Never hand-edit a built page: change the spec and rebuild.

## Loop

1. Start from a spec: `task artifact:new -- <dir>/<name>.json --kind graph|board|timeline|cards|layers|pivot|treemap|sankey|heatmap`, or extend an existing one. Schema: `tools/artifact_kit/SPEC.md` in Crepidoma.
2. Fill it from tool output (graph queries, task lists, TODO, test reports), not from reading files by hand. Ids stay stable across rebuilds so links and the `start` node keep working.
3. Build: `task artifact:build -- <spec>.json`. Spec errors print as `spec:<json path>: message`; fix them in the spec.
4. Lint: `task artifact:check -- <page>.html`. Zero errors before publishing; read each warning and fix it or know why it stays.
5. Publish with the Artifact tool: `file_path` is the built page, `icon` one generic word on the first publish, `description` one sentence. Later publishes reuse the same path, so the URL stays.
6. A copy committed to a repo is built with `--standalone` next to its spec.

## Widgets first

Show the relation, do not describe it. Each concept gets the widget that makes its shape visible (table in `SPEC.md`, "Pick the widget"); prose is the fallback for what no widget can carry. Detail lives in `note` fields, shown on hover or tap, never as inline paragraphs. `build` warns when text outweighs widgets; treat that warning as a redesign prompt.

## Spec rules

1. `title` is the page's name: two to four words, no explainer after a dash or colon. A project's own naming pattern wins.
2. Write in the language the readers use; set `lang` to match.
3. One fact per item. Item titles name the thing; notes say what it does or what it waits on.
4. Statuses, tones and categories encode real state, never decoration. Every board defines its `statuses`.
5. A graph sets `start`, so the page opens with a node selected and the panel filled.
6. Edges point from prerequisite to dependent. A cycle is a spec error: split the node or drop the weaker edge.

## Beyond the kit

A page the kit cannot express is written by hand in the same tokens (copy `tools/artifact_kit/kit.css`) and still passes `task artifact:check`. Add a section type to the kit when the same hand-written shape is needed twice.
