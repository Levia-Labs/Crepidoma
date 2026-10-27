# Ci

- GitHub Actions status, failure excerpts and watch.

## Contents

<!-- contents:start -->

- [`Taskfile.yml`](Taskfile.yml) - Task namespace with 4 tasks.
- [`ci_failures.py`](ci_failures.py) - Print only the failing test names, file:line lines and error lines of a PR or run.

<!-- contents:end -->

`task ci:failures -- <pr-number|run-id>` prints only failing test names, file:line and error lines (deduplicated, at most 40).
