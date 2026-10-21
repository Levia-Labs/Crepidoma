# Crepidoma

- The crepidoma plugin: directives, agents, hooks, skills and tools.

## Contents

<!-- contents:start -->

- [`.claude-plugin/`](.claude-plugin/README.md) - Plugin manifest with name and version.
- [`agents/`](agents/) - Subagents: Sonnet workers and the Haiku scout.
- [`bin/`](bin/README.md) - Executables added to PATH inside Claude sessions.
- [`directives/`](directives/README.md) - Main-thread rules injected at session start, capped at 8,500 characters.
- [`hooks/`](hooks/README.md) - Hook wiring: session and subagent start, tool guards, stop gate.
- [`scripts/`](scripts/README.md) - Stdlib tools behind hooks and task namespaces; contract in docs/contributing-tools.md.
- [`skills/`](skills/README.md) - Skills the plugin ships.
- [`tests/`](tests/README.md) - Pytest suite for the plugin scripts and manifests.
- [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) - Third-party notices

<!-- contents:end -->
