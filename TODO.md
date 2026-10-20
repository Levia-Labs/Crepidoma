# TODO

## 2 git:after-merge: treat an already-deleted branch as done

status: done
class: bug

task git:after-merge -- <repo> <branch> exits 1 with 'branch -D failed: branch not found' when the branch was already deleted (e.g. user ran gh pr merge --delete-branch and cleaned up). Should report it and exit 0.

## 3 rtk rewrites grep -q, breaking quiet exit status

status: open
class: bug

rtk's hook rewrote 'grep -q pattern file' in a wait loop to 'rtk grep -q', which does not return grep's -q exit status, so 'until ... grep -q' never ended. Exclude grep -q (rtk config hooks.exclude_commands) or report upstream.

## 4 spend:startup reports mcp 0 although transcripts carry mcp_instructions_delta

status: open
class: bug

An auditor transcript has a 2,065-char mcp_instructions_delta attachment, yet claude:spend:startup prints mcp 0 for every agent. Check the attachment matching in spend_startup.py.

## 5 hooks.py exceeds the 300-line cap

status: open
class: debt

plugins/crepidoma/scripts/hooks.py is 756 lines. Split it by hook event into modules under the cap.
