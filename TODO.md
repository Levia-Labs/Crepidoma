# TODO

## 3 rtk rewrites grep -q, breaking quiet exit status

status: open
class: bug

rtk's hook rewrote 'grep -q pattern file' in a wait loop to 'rtk grep -q', which does not return grep's -q exit status, so 'until ... grep -q' never ended. Exclude grep -q (rtk config hooks.exclude_commands) or report upstream.

## 5 quality:allowlist:dead misreads directory includes

status: open
class: debt

A pillar's quality:allowlist:dead check cannot read directory includes (.crepidoma/taskfiles/<dir>), so it reports live task names as dead. Resolve each include to <dir>/Taskfile.yml before collecting task names.
