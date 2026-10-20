# 0004. Taskfile as the interface

## Status

Accepted, 2026-10-20. Supersedes the per-pillar ADRs on this topic.

## Context

Projects accumulate entry points: a bootstrap script, a Makefile, loose scripts under a
`scripts/` folder, long container or virtual-environment invocations that differ between
operating systems. Each is found by a different person and none lists the others. Agents
working on a repository improvise the same commands repeatedly, each one a permission prompt
and a chance to get it wrong. Git hooks, CI and agent hooks drift when each spells out its own
version of a command.

## Decision

1. go-task is the only command runner. No Makefile, no `just`, no second runner beside it.
2. Every operation is a task. `task --list` is the complete index, and a tasks reference
   document explains what the list does not.
3. Every task has a `desc`. A task without one cannot be found, so `desc` is a requirement.
4. The root `Taskfile.yml` includes one Taskfile per domain. Includes give the
   `<domain>:<verb>` namespace; composite tasks such as setup are lists of `task:` references,
   so ordering lives in one place and each step stays runnable on its own.
5. Python is used where shell would be unreadable. Every script is reached through a task.
   Scripts accept `--help` and may be run directly, but the task is the documented way.
6. Shell embedded in a Taskfile is POSIX `sh`: no arrays, no `[[ ]]`, no `<<<`. The embedded
   blocks are extracted and linted as `sh`. Logic that becomes awkward in POSIX `sh` moves to
   a script.
7. Git hooks, CI and agent hooks call tasks. A hook entry and its manual run are one command.
8. Agents are allowed `task *`. Destructive tasks are denied to agents by name in the agent
   settings and additionally require `CONFIRM=yes`.

## Consequences

1. One place to look. A newcomer runs `task --list` and sees every capability, from full
   setup down to single steps.
2. One allowlist entry covers routine agent work. Destructive tasks are gated twice: the
   deny rule and the confirmation variable.
3. CI, git hooks and agent hooks run the same commands, so a gate cannot pass locally and
   fail in CI because of a different invocation.
4. `task` must be installed by hand before anything else works. It is the single documented
   manual step.
5. go-task's shell is `mvdan.cc/sh`, not bash. The POSIX `sh` rule keeps tasks independent of
   how much bash a given go-task version emulates, at the cost of some awkward logic.
6. shellcheck lints files, not YAML scalars. Embedded shell is checked only through the
   extraction step.
