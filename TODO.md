# TODO

## 1 Ship folder README task to pillars

status: open
class: tooling

Directive 14 asks every project for per-folder READMEs, but tools/folder_readme.py and docs:readmes live only in the root Taskfile; expose them through a shared namespace and pre-commit hook.

## 2 git:land fails with 'checks: none registered' now that Actions is disabled org-wide

status: open
class: bug

Actions disabled on every Levia-Labs repo 2026-10-31. taskfiles/git/land.py:148 raises when no checks register; add a no-checks path (flag or treat none-registered as pass after local gate). templates/ci.yml and .github/workflows still ship CI to pillars.
