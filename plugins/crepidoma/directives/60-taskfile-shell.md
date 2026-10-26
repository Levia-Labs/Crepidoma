# Taskfile shell

1. Write POSIX sh: the runner renders `{{...}}`, then runs `mvdan.cc/sh`, not bash. No arrays, `[[ ]]`, `<<<`; `task lint:embedded` checks blocks as sh (advisory), `task lint:sg` enforces the rules.
2. Invoke Python only via var `PY: '{{if eq OS "windows"}}python{{else}}python3{{end}}'` as `uv run {{.PY}}`; never `.venv/bin/python`. Outside the project: `uv run --no-project --python ">=3.12" "x.py"`, a script path, never a command name.
3. Pass root vars to includes via `vars: { PY: "{{.PY}}" }`; inheritance is unreliable.
4. Prefix included top-level vars with the namespace (`RUST_RUN`, not `RUN`); scope is shared, last loaded wins. Inspect with `task --verbose --dry <name>`.
5. `{{.TASKFILE_DIR}}` is the including file's directory; never append the repository path.
6. Write paths relative to the repository root; commands run there.
7. Never set `PATH` in `env:`; the runner ignores it. Resolve user binaries with `vars: TOOL: {sh: command -v tool || printf '%s' "${PIPX_BIN_DIR:-$HOME/.local/bin}/tool"}`.
8. Run locked dev-group tools via the locked environment runner; skip resolving.
9. Use `rm` then `mv`, never `mv -f`; shimmed coreutils fail on it.
10. Gate data-deleting tasks with `preconditions` on `CONFIRM=yes` plus a matching deny rule in `.claude/settings.json`.
