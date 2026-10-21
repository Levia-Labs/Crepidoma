# .claude

Project Claude Code configuration. Copy to `.claude/README.md` in the pillar and fill the `<placeholders>`.

## Own contents

1. `settings.json`: models, permissions, hooks, enabled plugins. Tracked.
2. `settings.local.json`: per-machine overrides. Gitignored.
3. `agents/<agent>.md`: `<one-line job; single job per agent>`.
4. `agents/<agent>.md`: `<one-line job>`.
5. `rules/<rule>.md`: `<what the rule enforces and when it loads>`.
6. `skills/<skill>/`: `<pillar-only skill; omit when none>`.

## From the Crepidoma plugin

1. Hooks: agent guard, model env guard, absolute-mode and skill-first reminders. Not copied here.
2. Generic agents, gates and skills: `<list from the plugin manifest>`. Not copied here.
3. Pillar files override plugin defaults of the same name; delete the override to fall back.
4. Plugin updates arrive through the marketplace; no local edits to plugin files.

## Skill-listing token cost

1. Every installed skill's description loads into every session, used or not.
2. Keep only needed plugins enabled in `enabledPlugins`; disable the rest per pillar.
3. A skill available from a plugin or global install is not copied into `skills/`.
4. Add a skill, agent or command only when `CLAUDE.md` requires it.

## Rules

1. Folder name equals the skill `name` frontmatter; every `SKILL.md` carries a `description`.
2. Agent `model:` is `<sonnet>`; `tools:` lists only the tools the agent calls.
3. Vendored files stay verbatim; refresh from upstream.
