# Git

- Read-only git views and the main-thread commit task.

## Contents

<!-- contents:start -->

- [`Taskfile.yml`](Taskfile.yml) - Task namespace with 8 tasks.
- [`commit_retry.py`](commit_retry.py) - Commit with one automatic retry when a hook only reformatted files.
- [`stage_paths.py`](stage_paths.py) - Stage exactly the given paths and print the staged list.

<!-- contents:end -->

`task git:stage -- <path>...` stages exactly the given paths and prints the staged list; it refuses no paths, `.` and paths outside the repo. Use it instead of `git add -A` when several agents share one checkout. `git:commit` retries once after formatter-only hook failures.
