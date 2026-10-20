---
paths:
  - "Taskfile.yml"
  - "**/Taskfile.yml"
  - "taskfiles/**"
---

Taskfile shell rules ship in Crepidoma directive 60; `task lint:taskfiles` enforces them.

1. Write POSIX sh in embedded blocks: no arrays, no `[[ ]]`, no `<<<`.
2. `PATH` cannot be set in `env:`; resolve the binary with `command -v` in `vars:` instead.
3. `{{.TASKFILE_DIR}}` is the including file's directory; never append the repository path to it.
4. Avoid `mv -f` and similar flags that coreutils shims lack; use `rm` then `mv`.
