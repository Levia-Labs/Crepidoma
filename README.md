# Crepidoma

> In classical Greek architecture, crepidoma is the foundation of one or more steps on which
> the superstructure of a building is erected. Usually the crepidoma has three levels,
> especially in Doric temples. However, exceptions are common: For example, the Heraion at
> Olympia features only two steps, and the Olympeion at Agrigento, Sicily has four.
>
> — [Crepidoma, Wikipedia](https://en.wikipedia.org/wiki/Crepidoma)

![Crepidoma, stereobate and stylobate](https://upload.wikimedia.org/wikipedia/commons/3/39/Crepidoma-stereobate-stylobate.svg)

<sub>"[Crepidoma-stereobate-stylobate.svg](https://commons.wikimedia.org/wiki/File:Crepidoma-stereobate-stylobate.svg)"
by Gleb713, licensed [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), via
Wikimedia Commons. Shown unmodified.</sub>

Crepidoma is the stepped base of Levia Labs. Every pillar project stands on it: one source for
LLM directives, Claude Code agents and hooks, commit gates, shared lint, format and security
configs, Taskfiles and process ADRs. Pillars link Crepidoma; nothing is copied.

## Adopt in a pillar

1. Claude Code plugin, in `.claude/settings.json`:

   ```json
   {
     "extraKnownMarketplaces": {
       "levia-labs": { "source": { "source": "github", "repo": "Levia-Labs/Crepidoma" } }
     },
     "enabledPlugins": { "crepidoma@levia-labs": true }
   }
   ```

   Each collaborator installs once, from the CLI:

   ```sh
   claude plugin install crepidoma@levia-labs --scope project
   ```

   or inside Claude Code: `/plugin install crepidoma --marketplace Levia-Labs/Crepidoma`.

   The committed `enabledPlugins` entry is also the opt-in that lets the plugin's hooks run the
   pillar's own task gates.

2. Taskfiles and configs, as a submodule:

   ```sh
   git submodule add https://github.com/Levia-Labs/Crepidoma .crepidoma
   ```

   ```yaml
   includes:
     claude: .crepidoma/taskfiles/claude
     lint: .crepidoma/taskfiles/lint
   ```

3. Commit gates, in `.pre-commit-config.yaml`:

   ```yaml
   repos:
     - repo: https://github.com/Levia-Labs/Crepidoma
       rev: v0.1.0
       hooks:
         - id: crepidoma-scrub
         - id: crepidoma-long-files
   ```

Full steps, the third-party plugin list and every shared gate: [docs/migration.md](docs/migration.md)
and [templates/](templates/).

## What the plugin does

1. SessionStart: injects the shared directives (communication style, tool-first loop,
   conventions, models, skills and plugins, Taskfile shell), capped at 10,000 characters.
2. PreToolUse: refuses raw whole-file reads in the main thread (`digest` is the bounded reader),
   refuses forbidden or excess subagents, and stops subagents from discarding working-tree changes.
3. PostToolUse and Stop: marks edited scopes dirty and runs the project's gate before a turn ends.
4. Agents: auditor, diff-reviewer, docs-syncer, gate-fixer, implementer, rule-smith,
   todo-triage, toolsmith.

## Contents

| Path                            | What                                                                                                                   |
| ------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| `plugins/crepidoma/directives/` | Always-on rules, injected at session start                                                                             |
| `plugins/crepidoma/agents/`     | Shared subagents                                                                                                       |
| `plugins/crepidoma/hooks/`      | Hook wiring for the scripts below                                                                                      |
| `plugins/crepidoma/scripts/`    | `inject_directives.py`, `raw_read_guard.py`, `hooks.py`, `digest.py`                                                   |
| `configs/`                      | editorconfig, gitattributes, prettier, eslint, ruff, yamllint, ast-grep, gitleaks, semgrep, zizmor, hadolint, tsconfig |
| `taskfiles/`                    | Shared `claude:` and `lint:` Taskfile namespaces                                                                       |
| `tools/`                        | scrub, ratchet (300-line long-file threshold), drift check, denylist, release                                          |
| `docs/adr/`                     | Process decisions shared by all pillars                                                                                |
| `templates/`                    | Files a pillar copies once                                                                                             |

## Working on Crepidoma

```sh
task setup      # uv sync + git hooks
task validate   # everything CI runs
task --list     # all tasks
```

Every commit runs the pre-commit gates, including `crepidoma-scrub`, which rejects local paths,
emails, tokens and private repo names. The repo is public, so nothing private may land here.

## License

Repository content: [MIT](LICENSE). README image: CC BY-SA 4.0, see attribution above.
