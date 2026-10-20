# TODO

## 1 pillar-migrator: add submodules: true to kept CI checkouts

status: open
class: bug

When a pillar keeps its own CI workflows, every actions/checkout that runs task needs submodules: true. RailGame CI failed with 'No Taskfile found at .crepidoma/taskfiles/claude' until fixed in RailGame bc7ad22.
