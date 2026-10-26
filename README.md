<div align="center">

<img src="docs/logo.svg" alt="Crepidoma logo: three columns on a stepped base" width="120">

# Crepidoma

**The foundation every Levia Labs project stands on.**

One Claude Code plugin, shared Taskfiles, lint configs and commit gates.<br>
Projects link it, never copy it, so nothing drifts.

[![validate](https://github.com/Levia-Labs/Crepidoma/actions/workflows/validate.yml/badge.svg)](https://github.com/Levia-Labs/Crepidoma/actions/workflows/validate.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Claude Code plugin](https://img.shields.io/badge/Claude%20Code-plugin-d97757.svg)](plugins/crepidoma/README.md)

</div>

## Why

- **One source of truth** for LLM directives, agents, hooks, gates, configs, Taskfiles and process ADRs.
- **Linked, not copied**: every project pulls the same version, and an update reaches all of them.
- **Lean agents**: every turn is a tool call with a small receipt, so sessions use fewer tokens.

## Quick start

1. Enable the plugin in your project's `.claude/settings.json`:

   ```json
   {
     "extraKnownMarketplaces": {
       "levia-labs": {
         "source": { "source": "github", "repo": "Levia-Labs/Crepidoma", "ref": "main" }
       }
     },
     "enabledPlugins": { "crepidoma@levia-labs": true }
   }
   ```

   ```sh
   claude plugin install crepidoma@levia-labs --scope project
   ```

2. Add Taskfiles and configs as a submodule, then include the namespaces you need:

   ```sh
   git submodule add -b main https://github.com/Levia-Labs/Crepidoma .crepidoma
   ```

   ```yaml
   includes:
     claude: .crepidoma/taskfiles/claude
     git: .crepidoma/taskfiles/git
     quality: .crepidoma/taskfiles/quality
   ```

3. Turn on the commit gates in `.pre-commit-config.yaml`:

   ```yaml
   repos:
     - repo: https://github.com/Levia-Labs/Crepidoma
       rev: main
       hooks:
         - id: crepidoma-scrub
         - id: crepidoma-long-files
   ```

Full steps are in [docs/migration.md](docs/migration.md). From a Crepidoma session, the `migrate-pillar` skill does the whole migration for you.

## What you get

| Layer          | Highlights                                                                                                  |
| -------------- | ----------------------------------------------------------------------------------------------------------- |
| **Directives** | Communication style, tool-first loop, conventions, model tiers, shell and safety                            |
| **Models**     | Opus orchestrates, Sonnet works, Haiku reads and indexes                                                    |
| **Hooks**      | Compact subagent harness, raw-read guard, subagent and git policy, stop gate                                |
| **Agents**     | 15 single-job agents, from `scout` and `implementer` to `security-reviewer` and `pillar-migrator`           |
| **Skills**     | `docs-sweep`, `migrate-pillar`, `python-patterns`, `python-testing`                                         |
| **Tasks**      | `claude`, `repo`, `todo`, `git`, `graph`, `test`, `quality`, `security`, `ci`, `lint`, `setup`, `go`, `rtk` |
| **Configs**    | ruff, pyright, prettier, eslint, yamllint, ast-grep, semgrep, gitleaks, zizmor, hadolint                    |
| **Decisions**  | [Architecture decision records](docs/adr/README.md)                                                         |

## Levia Labs open source

| Project                                                        | What it does                                               |
| -------------------------------------------------------------- | ---------------------------------------------------------- |
| [Crepidoma](https://github.com/Levia-Labs/Crepidoma)           | LLM tooling foundation for every Levia Labs project        |
| [beat-analyser](https://github.com/Levia-Labs/beat-analyser)   | Reads beat data from music files with madmom, dockerized   |
| [saber-tooth](https://github.com/Levia-Labs/saber-tooth)       | Beat Saber modding API for custom levels                   |
| [HumanShortCode](https://github.com/Levia-Labs/HumanShortCode) | Turns long, unreadable ids into short human-readable codes |
| [QC2C](https://github.com/Levia-Labs/QC2C)                     | Quick coordinates-to-country lookup                        |

## Repository map

- [`plugins/crepidoma/`](plugins/crepidoma/README.md): the Claude Code plugin
- [`taskfiles/`](taskfiles/README.md): shared task namespaces
- [`configs/`](configs/README.md): shared lint, format and security configs
- [`templates/`](templates/README.md): files a project copies once
- [`tools/`](tools/README.md): scrub, ratchet, drift, denylist, release and folder README tools
- [`docs/`](docs/README.md): guides, ADRs and design history

## Contributing

```sh
task setup      # uv sync and git hooks
task validate   # everything CI runs
task --list     # every task
```

Every commit runs the gates, including `crepidoma-scrub`, which blocks local paths, emails, tokens and private names because the repo is public. Every folder keeps a README; `task docs:readmes` refreshes them.

<details>
<summary><b>About the name</b></summary>

> In classical Greek architecture, crepidoma is the foundation of one or more steps on which the superstructure of a building is erected.
>
> <p align="right"><a href="https://en.wikipedia.org/wiki/Crepidoma">Crepidoma, Wikipedia</a></p>

<p align="center"><img src="docs/crepidoma.svg" alt="Crepidoma with a pillar bracket above it" width="480"></p>

<sub>Image: "<a href="https://commons.wikimedia.org/wiki/File:Crepidoma-stereobate-stylobate.svg">Crepidoma-stereobate-stylobate.svg</a>" by Gleb713, <a href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</a>, via Wikimedia Commons; cropped, relabelled with a pillar bracket, white background added.</sub>

</details>

## License

Code, docs and logo are [MIT](LICENSE). The Wikimedia diagram under "About the name" is CC BY-SA 4.0, credited there.
