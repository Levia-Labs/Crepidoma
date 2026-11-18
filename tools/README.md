# Tools

- Repo tools: scrub, ratchet, drift, denylist, release, pin, folder READMEs.
- Folder README purposes: `[files]` keys in the purposes TOML may be repo-relative paths (forward slashes on every OS) with the basename as fallback; `include = ["docs/folder-purposes.d/*.toml"]` merges more files (duplicate keys are an error); `task docs:purpose -- <path> "<text>" [--replace]` sets one and refreshes the READMEs.

## Contents

<!-- contents:start -->

- [`artifact_kit/`](artifact_kit/README.md) - Stylesheet and scripts the artifact builder inlines into a page.
- [`artifact.py`](artifact.py) - Build self-contained claude.ai artifact pages from a JSON spec.
- [`artifact_budget.py`](artifact_budget.py) - Text budget of an artifact page: warnings when prose outweighs the widgets.
- [`artifact_check.py`](artifact_check.py) - Lint claude.ai artifact HTML pages against the publish rules.
- [`artifact_check_css.py`](artifact_check_css.py) - CSS-side rules of artifact_check: stylesheet parsing, theme tokens and literal colours.
- [`artifact_examples.py`](artifact_examples.py) - Small working example specs, one per kind, for `artifact.py new`.
- [`artifact_shapes.py`](artifact_shapes.py) - Field shapes of each artifact section type, and the whole-graph checks.
- [`artifact_shot.py`](artifact_shot.py) - Screenshot an artifact page with a headless browser, in a forced colour theme.
- [`artifact_spec.py`](artifact_spec.py) - Validation of an artifact page spec; see artifact_kit/SPEC.md for the schema.
- [`artifact_widgets.py`](artifact_widgets.py) - Shapes and cross-checks of the correlation widgets: layers, pivot, treemap, sankey, heatmap.
- [`code_refs.py`](code_refs.py) - List references to a symbol in tracked source files.
- [`denylist.py`](denylist.py) - Write the scrub denylist: names of private or remote-less repos under a pillars directory.
- [`drift_check.py`](drift_check.py) - Compare a pillar checkout with Crepidoma-owned files.
- [`drift_map.toml`](drift_map.toml) - Crepidoma files and where pillars kept copies.
- [`edit_file.py`](edit_file.py) - Exact text replacement and insertion in one file, with a one-line receipt.
- [`folder_readme.py`](folder_readme.py) - Keep a README.md in every tracked folder with a generated contents list.
- [`jscpd_pct.py`](jscpd_pct.py) - Print the total duplicated-lines percent from a jscpd JSON report.
- [`path_guard.py`](path_guard.py) - Path guard shared by tools that write files named on the command line.
- [`pin_pillar.py`](pin_pillar.py) - Pin a pillar's Crepidoma submodule to a release tag without discarding changes.
- [`ratchet.py`](ratchet.py) - Ratchet quality metrics so they never get worse.
- [`read_range.py`](read_range.py) - Print numbered line ranges of one or more files, at most 60 lines per call.
- [`release.py`](release.py) - Bump the plugin version, prepend a CHANGELOG entry, commit and tag. Never pushes.
- [`review_files.py`](review_files.py) - Review helpers that keep big text out of the chat: write it to a file, print the path.
- [`scrub_check.py`](scrub_check.py) - Fail when files carry local paths, emails, tokens or denylisted names.
- [`sdd_ledger.py`](sdd_ledger.py) - SDD ledger helpers: append a progress line, defer Low/Minor review findings as TODO entries.

<!-- contents:end -->
