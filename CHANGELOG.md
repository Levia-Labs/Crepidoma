# Changelog

## v0.6.0 - 2026-10-30

## v0.5.0 - 2026-10-27

## Unreleased

- fix(security): `review:diff` rejects option-like BASE/HEAD/paths and verifies revisions; `edit:*` and `sdd:*` write only inside the git toplevel, never inside the git directory or `.claude/` (edit also refuses settings, hooks and pre-commit config files); `go:fuzz` passes FUZZTIME through `env:`
- feat(hooks): `pre-bash` refuses, for the main thread and subagents, stdin-reading interpreters (`python -`, heredocs into an interpreter), kill by name or image (`taskkill /IM`, `pkill`, `killall`, `Stop-Process -Name`) and raw `git commit` (use `task git:commit`); `git add -A/./--all` stays refused for subagents
- feat(digest): kind-aware default body (Markdown headings, code definitions, log failures, first and last 5 lines); new `task repo:digest`; the raw-read refusal names it

- feat(folder_readme): `[files]` purposes key on the repo-relative path first (basename fallback); `include` globs merge extra purposes files; `task docs:purpose -- <path> "<text>"` sets a purpose and refreshes READMEs

- fix(semgrep): include patterns match at the repo root and nested (`**/Taskfile.yml` etc.), so consumer runs no longer warn and exit 201
- feat(git): `git:commit` retries once when a hook only reformatted files, lists staged long files first and prints failed hook lines, commit id and push status; new `git:stage -- <path>...` stages exactly the given paths (subagent-safe in a shared checkout)
- feat(ci): `ci:failures -- <pr-number|run-id>` prints deduplicated failing test names, file:line and error lines of the latest failed run (at most 40)
- feat(quality): `quality:long-files:staged` lists staged files over the line cap

- feat(tasks): `edit` (`replace`, `insert-after`), `sdd` (`progress`, `defer`), `review` (`diff`, `relay`) and `code` (`refs`) namespaces and `repo:read`, replacing hand-written edit, ledger, review-relay and grep commands
- feat(go): `go` task namespace (check, fmt, fuzz, race) and pre-commit hooks `go-check` and `go-fmt`
- fix(lint): pre-commit eslint hook uses `npx --no-install` so `--config` is honoured; shared eslint config defines browser globals for web/static/public/`*.browser.js` and node globals for `*.mjs`/scripts
- fix(lint): complete browser and node globals; scope `.mjs` (browser dirs get browser globals) and `.cjs` (commonjs); add `CSS`; ignore `.venv`, `venv`, `.tox` and `.crepidoma`
- fix(quality): parse jscpd 5 JSON report and skip vendored .crepidoma and .worktrees lanes in bandit; consumer bandit baselines may drop and should be ratcheted down
- fix(settings): deny allowlist escape flags for task, pre-commit, git commit and git diff/log/show
- fix(settings): deny abbreviated `--no-v*` and `--ext*` flags (git rejects `--no-i`/`--no-in`/`--no-ind` for diff) and pin the `levia-labs` marketplace ref to a release tag; `release.py` now bumps that ref
- fix(settings): drop the `git commit *` allow so combined short flags (`-an`, `-nm`) cannot skip hooks; commit through `task git:commit` or approve the prompt. Consumers resync `.claude/settings.json` (see docs/migration.md)

## v0.4.3 - 2026-10-26

## v0.4.2 - 2026-10-22

## v0.4.1 - 2026-10-21

## v0.4.0 - 2026-10-21

## v0.3.2 - 2026-10-21

## v0.3.1 - 2026-10-21

## v0.3.0 - 2026-10-21

## v0.2.0 - 2026-10-21

## v0.1.1 - 2026-10-20

## v0.1.0 - 2026-10-20
