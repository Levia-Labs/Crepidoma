# Skills and plugins

1. Keep project-local skills in `.claude/skills/`, enable shared plugins in `.claude/settings.json`, and list both in `.claude/README.md`.
2. Let process skills trigger on their own descriptions. Before acting, apply the matching skill:
   1. Creative work: brainstorming.
   2. New UI or redesign: frontend design.
   3. Multi-file feature: feature development (explorer, architect and reviewer agents).
   4. Bug or test failure: systematic debugging and test-driven development.
   5. Claiming work is done: verification before completion.
   6. Diff or pull request: code review.
3. Run a humanizing skill over prose others read: docs, ADRs, PR bodies, site copy.
4. Apply terse output modes to chat replies only; write code, comments, commits, docs, security warnings and anything others read in normal English.

## graphify

1. graphify is an optional third-party skill that builds a queryable knowledge graph of a repository. On `/graphify`, use the installed skill before anything else.
2. Where a project ships a graph, query it only through project tasks, never by calling graphify directly.
3. For cross-file questions ("what calls X", "what depends on Y"), query the graph before any grep. Use a path query for two nodes, an explain query for one concept.
4. Never read `graphify-out/GRAPH_REPORT.md` whole; run a scoped query instead.
5. After code changes, refresh the graph with the AST-only update. Run model-based extraction only after documentation changes, on the smallest model.
