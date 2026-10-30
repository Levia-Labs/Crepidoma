#!/bin/sh
# Exit 0 when the current directory is inside the repo that contains $1.
# `task -d <repo>` retargets ROOT_DIR but not USER_WORKING_DIR, so git tasks that run in
# USER_WORKING_DIR would silently act on the shell's repo; the Taskfile refuses on mismatch.
here=$(git rev-parse --show-toplevel 2>/dev/null) || exit 1
there=$(git -C "$1" rev-parse --show-toplevel 2>/dev/null) || exit 1
[ "$here" = "$there" ]
