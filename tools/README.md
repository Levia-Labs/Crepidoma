# Tools

- Repo tools: scrub, ratchet, drift, denylist, release, folder READMEs.

## Contents

<!-- contents:start -->

- [`denylist.py`](denylist.py) - Write the scrub denylist: names of private or remote-less repos under a pillars directory.
- [`drift_check.py`](drift_check.py) - Compare a pillar checkout with Crepidoma-owned files.
- [`drift_map.toml`](drift_map.toml) - Crepidoma files and where pillars kept copies.
- [`folder_readme.py`](folder_readme.py) - Keep a README.md in every tracked folder with a generated contents list.
- [`ratchet.py`](ratchet.py) - Ratchet quality metrics so they never get worse.
- [`release.py`](release.py) - Bump the plugin version, prepend a CHANGELOG entry, commit and tag. Never pushes.
- [`scrub_check.py`](scrub_check.py) - Fail when files carry local paths, emails, tokens or denylisted names.

<!-- contents:end -->
