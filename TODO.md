# TODO

## 3 rtk rewrites grep -q, breaking quiet exit status

status: open
class: bug

rtk's hook rewrote 'grep -q pattern file' in a wait loop to 'rtk grep -q', which does not return grep's -q exit status, so 'until ... grep -q' never ended. Exclude grep -q (rtk config hooks.exclude_commands) or report upstream.

## 4 hooks.py facade forwards setattr only for tests

status: open
class: debt

hooks.py swaps its module class to _Facade so tests that patch hooks.ROOT, hooks.LEDGER or hooks.run reach the split parts. Patch the owning hooks_* module in test_hooks_py.py, test_lanes.py and lanes.py, then drop _Facade.

## 5 quality:allowlist:dead misreads directory includes

status: open
class: debt

A pillar's quality:allowlist:dead check cannot read directory includes (.crepidoma/taskfiles/<dir>), so it reports live task names as dead. Resolve each include to <dir>/Taskfile.yml before collecting task names.
