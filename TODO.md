# TODO

## 1 pillar-migrator: add submodules: true to kept CI checkouts

status: open
class: bug

When a pillar keeps its own CI workflows, every actions/checkout that runs task needs submodules: true. RailGame CI failed with 'No Taskfile found at .crepidoma/taskfiles/claude' until fixed in RailGame bc7ad22.

## 2 git:after-merge: treat an already-deleted branch as done

status: done
class: bug

task git:after-merge -- <repo> <branch> exits 1 with 'branch -D failed: branch not found' when the branch was already deleted (e.g. user ran gh pr merge --delete-branch and cleaned up). Should report it and exit 0.
