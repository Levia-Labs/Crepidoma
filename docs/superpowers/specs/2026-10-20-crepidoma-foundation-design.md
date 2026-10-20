# Crepidoma foundation: design

Date: 2026-10-20. Status: approved design, pending spec review.

> In classical Greek architecture, crepidoma is the foundation of one or more steps on which the superstructure of a building is erected.
> (Wikipedia, "Crepidoma")

## 1. Intent

1. Outcome: one public repo, `github.com/Levia-Labs/Crepidoma`, is the single source of the LLM directives, agents, hooks, scripts, commit gates, shared configs, process ADRs and Taskfiles that pillar repos currently copy between each other.
2. Consumers: Levia Labs pillar repos and the maintainer's user-scope Claude Code setup.
3. Success criteria:
   1. A pillar adopts Crepidoma by committing three references: a marketplace + `enabledPlugins` block in `.claude/settings.json`, a `.crepidoma` git submodule, and a `repo: https://github.com/Levia-Labs/Crepidoma` entry in `.pre-commit-config.yaml`.
   2. No secret, credential, email, absolute local path or private repo name ever reaches the public remote.
   3. Crepidoma runs its own gates on every commit and push.
   4. `claude plugin validate .` passes; every script has tests.
4. Out of scope for this iteration: migration PRs in pillar repos (documented in `docs/migration.md`, executed later, one PR per repo).

## 2. Decisions

1. Distribution: Claude Code plugin marketplace for Claude assets; git submodule `.crepidoma` for Taskfiles and configs; pre-commit remote repo for gates.
2. Communication-style directives (no first person, droid tone, numbered lists) are part of `crepidoma-core`, applied in every pillar.
3. Third-party content (graphify, humanizer, skill-creator, superpowers, caveman, feature-dev, frontend-design, security-guidance, other installed plugins) is referenced, never vendored. The settings template lists their marketplaces and `enabledPlugins` entries.
4. Drifted copies are merged into a superset per file. Conflicting lines are recorded in `docs/superpowers/specs/merge-conflicts.md` for maintainer review. Repo-specific rules stay in the pillar and are listed as such in `docs/migration.md`.
5. Formatter and linter consolidation: `ruff format` replaces black; prettier + eslint replace biome; pyright/basedpyright are opt-in per pillar.
6. Pillar inventory data (repo names, local paths) stays out of the repo. Public docs say "pillar repos" generically.

## 3. Platform constraints (code.claude.com/docs)

1. CLAUDE.md `@import` accepts local paths only (memory.md). Directives therefore reach sessions through a plugin SessionStart hook emitting `hookSpecificOutput.additionalContext`, capped at 10,000 characters (hooks.md).
2. A plugin ships skills, agents, commands, hooks, MCP/LSP servers, `bin/` executables and output styles. Plugin `settings.json` honours only `agent` and `subagentStatusLine`; permissions and `statusLine` stay in templates (plugins/components.md).
3. A committed `extraKnownMarketplaces` registers the marketplace after folder trust; each collaborator runs `claude plugin install crepidoma-core@crepidoma --scope project` once (plugins/loading.md).
4. Hook commands reference bundled files through `${CLAUDE_PLUGIN_ROOT}`, quoted. Version pinning: `ref` / `sha` in the source object, `version` in `plugin.json`.

## 4. Repository layout

```
.claude-plugin/marketplace.json        marketplace "crepidoma"
plugins/crepidoma-core/
  .claude-plugin/plugin.json
  directives/                          communication-style, tool-first-loop, conventions,
                                       models, skills-and-plugins, taskfile-shell
  agents/                              merged superset (auditor, implementer, toolsmith, translator, ...)
  hooks/hooks.json                     SessionStart -> inject_directives; PreToolUse -> raw_read_guard
  scripts/                             inject_directives.py, raw_read_guard.py, hooks.py
  bin/digest                           bounded output digest, on PATH inside sessions
  tests/
.pre-commit-hooks.yaml                 gate hooks consumable by pillars
configs/                               .editorconfig, .gitattributes, .prettierrc, eslint.config.js,
                                       ruff.toml, .yamllint, sgconfig.yml + ast-grep/rules/,
                                       gitleaks.toml, semgrep/, zizmor.yml, .hadolint.yaml, tsconfig.base.json
taskfiles/claude/Taskfile.yml          shared claude:* tasks
taskfiles/lint/Taskfile.yml            shared lint:* tasks
tools/                                 scrub_check.py, drift_check.py, ratchet.py (+ tests)
docs/adr/                              process ADRs + template
docs/migration.md                      pillar and user-scope adoption steps
templates/                             pillar settings.json, CLAUDE.md skeleton, .pre-commit-config.yaml, .gitmodules
.github/workflows/validate.yml         CI = task validate
.github/dependabot.yml
Taskfile.yml                           root interface for working on this repo
README.md
```

## 5. Components

1. `inject_directives.py`: reads `directives/*.md` in name order, concatenates, prints SessionStart JSON. Exit 0 always; on read failure emits a one-line warning as context instead of crashing the session. Test: output under 10,000 characters, valid JSON, stable order.
2. `raw_read_guard.py`: canonical version taken from the pillar copy identical to `~/.claude/bin/raw_read_guard.py`. Denies raw whole-file reads in the main thread, allows subagents. Tests: allow/deny table.
3. `digest`: caps output to 20 lines / 1 KB with `--grep`, `--tail`, `--max-bytes`. Tests: bounds, stdin and file input.
4. `hooks.py`: superset of the three drifted pillar copies.
5. `scrub_check.py`: scans staged or given files for absolute user paths (`[A-Z]:\\Users\\`, `[A-Z]:\\Projects`), emails, token patterns, and names from a gitignored denylist (`.scrub-denylist`, template committed as `.scrub-denylist.example`). Exit 1 with `file:line: rule` on hit.
6. `drift_check.py`: input pillar path; compares pillar copies of Crepidoma-owned files (by mapping table) and reports identical / drifted / missing. Output bounded; full report written to a file.
7. `ratchet.py`: long-files, coverage and duplication ratchets against per-repo baseline files; fails when a metric worsens, rewrites the baseline when it improves with `--update`.

## 6. Gates

1. pre-commit stage (staged files, fast): prettier, eslint, ruff check, ruff format --check, yamllint, shellcheck, ast-grep scan, gitleaks protect, scrub_check, long-files ratchet.
2. pre-push stage: all of the above plus semgrep, zizmor, actionlint, hadolint, osv-scanner, pip-audit, npm audit, pytest, `claude plugin validate .`.
3. CI: `task validate` equals pre-push; Dependabot for GitHub Actions, pip and npm.
4. Hook manager: pre-commit. Crepidoma publishes `.pre-commit-hooks.yaml` with ids `crepidoma-scrub`, `crepidoma-ratchet-long-files`, `crepidoma-drift` and wrappers for shared-config tools.

## 7. Root Taskfile

`setup`, `fmt`, `lint`, `sec`, `test`, `plugin:validate`, `drift -- <path>`, `hooks:pre-commit`, `hooks:pre-push`, `validate`, `release -- <version>`.

## 8. Build order

1. Commit gates and root Taskfile, active on Crepidoma itself.
2. scrub_check + gitleaks before the first push.
3. Plugin skeleton, injector, guard, digest, tests.
4. Merges (agents, hooks.py, Taskfiles, directives, configs, ADRs) by named merge agents; unread sources (`tasks/precommit`, `tasks/git`, a pillar `Tasks/qa`, pillar lint commands) are read here.
5. ADRs, templates, migration guide, README.
6. After build: user-scope install of `crepidoma-core`; global `~/.claude/CLAUDE.md` reduced to personal content; `~/.claude/bin` removed with backup.

## 9. README

1. Wikipedia lead quote with link to https://en.wikipedia.org/wiki/Crepidoma.
2. Image `https://upload.wikimedia.org/wikipedia/commons/3/39/Crepidoma-stereobate-stylobate.svg`, attribution: "Crepidoma-stereobate-stylobate.svg" by Gleb713, CC BY-SA 4.0, via Wikimedia Commons, linked to the file page and license.
3. Metaphor: Crepidoma is the stepped base; pillar projects stand on it.
4. Adoption: the three references from 1.3.1, copy-paste ready.
5. Contents map and Taskfile usage.

## 10. Error handling

1. Hooks never block a session on internal failure: injector and guard fail open with a warning, except the guard's explicit deny path.
2. Gate tools fail closed: any hit or tool error exits non-zero.
3. Missing optional tools in a pillar (e.g. no JS) skip via pre-commit `types` filters, not via silent failure.
