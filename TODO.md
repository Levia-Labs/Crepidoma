# TODO

## 1 Ship folder README task to pillars

status: open
class: tooling

Directive 14 asks every project for per-folder READMEs, but tools/folder_readme.py and docs:readmes live only in the root Taskfile; expose them through a shared namespace and pre-commit hook.

## 2 git:land fails with 'checks: none registered' now that Actions is disabled org-wide

status: open
class: bug

Actions disabled on every Levia-Labs repo 2026-10-31. taskfiles/git/land.py:148 raises when no checks register; add a no-checks path (flag or treat none-registered as pass after local gate). templates/ci.yml and .github/workflows still ship CI to pillars.

## 3 artifact kit: treemap tap zooms at once on touch

status: open
class: bug

tools/artifact_kit/treemap.js: emulated hover and click arrive together on touch, so a tap zooms instead of showing the tooltip first.

## 4 artifact kit: graph leaves blank space under short columns

status: open
class: bug

tools/artifact_kit/graph.js: pages with one tall column (10 nodes) leave empty space below the shorter columns.

## 5 artifact kit: UI dictionary covers en and pl only

status: open
class: tooling

tools/artifact_kit/ui.json: any other lang falls back to en unless the spec supplies ui.

## 6 artifact kit: verify layout and touch on a real phone

status: open
class: tooling

Only checked at 400px through an iframe wrapper (headless Edge has a minimum window width); touch never tested on a device.
