# Migrating a pillar to Crepidoma

## Pillar repo

1. Add the submodule: run the two commands in `templates/gitmodules.txt`; set `submodules: true` on every kept CI `actions/checkout` that runs `task`.
2. Merge `templates/Taskfile.includes.yml` into the pillar `Taskfile.yml`; delete the pillar's own
   `tasks/claude` and `tasks/lint` directories (or `Tasks/...`).
3. Merge `templates/settings.json` into `.claude/settings.json`; delete the pillar hooks block that
   ran `hooks.py` or `raw_read_guard.py`. The committed `enabledPlugins` entry is also the opt-in
   that lets the plugin's hooks run the pillar's task gates.
4. Each collaborator runs once: `claude plugin install crepidoma@levia-labs --scope project`.
5. Replace `.pre-commit-config.yaml` with `templates/.pre-commit-config.yaml`, keep pillar-only
   hooks, then run `pre-commit install && pre-commit autoupdate`.
6. Point root configs at `.crepidoma/configs/`:
   1. `pyproject.toml`: `[tool.ruff]` `extend = ".crepidoma/configs/ruff.toml"`.
   2. `.gitleaks.toml`: `[extend]` `path = ".crepidoma/configs/gitleaks.toml"`.
   3. `tsconfig.json`: `"extends": "./.crepidoma/configs/tsconfig.base.json"`.
   4. `eslint.config.js`: import and spread `.crepidoma/configs/eslint.config.js`, then add framework plugins.
   5. `.editorconfig`, `.gitattributes`, `.prettierrc`, `.yamllint`: tools read these from the repo
      root, so keep identical copies; `task drift` reports when they fall out of sync.
7. Shrink `CLAUDE.md` to `templates/CLAUDE.md` plus repo-specific rules.
8. Replace process ADRs with stubs: "Superseded by Crepidoma ADR-000N", linking
   `https://github.com/Levia-Labs/Crepidoma/blob/main/docs/adr/`.
9. From the Crepidoma checkout run `task drift -- <pillar path>` until it reports
   `duplicate=0 drifted=0` (root config copies from step 6.5 report as `mirror`).
   A copy that keeps all shared content and adds pillar-only content (Unity LFS lines, extra
   `sgconfig.yml` ruleDirs) reports as `extended` once the pillar declares it in
   `.crepidoma-drift.toml`: one `[[extended]]` table per file with `path` and an optional `waive`
   list of shared facts the pillar intentionally drops. Facts are whitespace-normalised lines;
   for `.yml` files `key|- item` or `key|key: value`, keyed by the top-level key. A missing,
   unwaived shared fact or an altered value stays `drifted`.
10. Open one PR per pillar.

## Optional pillar files

1. `templates/AGENTS.md` to `.github/instructions/AGENTS.md`; `templates/copilot-instructions.md` to
   `.github/copilot-instructions.md`.
2. `templates/claude-README.md` to `.claude/README.md`; `templates/rules/taskfile-shell.md` to
   `.claude/rules/taskfile-shell.md`.
3. `templates/rtk-filters.toml` to `.rtk/filters.toml`.
4. `templates/ci.yml` to the pillar's `ci.yml` workflow (calls Crepidoma's reusable workflow).
5. Drop pillar copies of budget, rate, history, tokens, lanes, sessions, outline, section, todo, docs
   and gate scripts; the shared namespaces replace them.

## User scope

1. Back up `~/.claude/CLAUDE.md`, `~/.claude/settings.json` and `~/.claude/bin/`.
2. Run `claude plugin marketplace add Levia-Labs/Crepidoma`, then
   `claude plugin install crepidoma@levia-labs --scope user`.
3. Remove the PreToolUse `raw_read_guard.py` hook from `~/.claude/settings.json`.
4. Reduce `~/.claude/CLAUDE.md` to personal content; delete `~/.claude/bin/digest.py` and
   `~/.claude/bin/raw_read_guard.py`.

## Config overrides

Shared `lint`, `security` and `quality` read `LINT_CFG`, `SECURITY_CONFIGS` and `QUALITY_CONFIGS` (default: Crepidoma `configs/`). Override per include with `vars: { LINT_CFG: "{{.ROOT_DIR}}" }`, the CLI or the environment. Shared gitleaks uses a repo-root `.gitleaks.toml` when present; let it extend the shared config.

## Commit message scrub

Add `- id: crepidoma-scrub-msg` under the Crepidoma hooks and `commit-msg` to `default_install_hook_types`, then run `task setup:hooks` so the commit-msg hook installs. Scrub a drafted PR body before `gh pr create` with `task repo:scrub:text -- <file>`.
