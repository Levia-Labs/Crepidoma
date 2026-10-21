# TODO

## 5 quality:allowlist:dead misreads directory includes

status: open
class: debt

A pillar's quality:allowlist:dead check cannot read directory includes (.crepidoma/taskfiles/<dir>), so it reports live task names as dead. Resolve each include to <dir>/Taskfile.yml before collecting task names.
