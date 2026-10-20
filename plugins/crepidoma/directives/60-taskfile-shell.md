# Taskfile shell

1. Write POSIX sh: the runner substitutes `{{...}}`, then runs its own interpreter (`mvdan.cc/sh`), not bash. No arrays, no `[[ ]]`, no `<<<`; lint embedded blocks as sh.
2. Keep tasks portable across Windows and Linux: reference interpreters through Taskfile vars, never `.venv/bin/python` or `python3`.
3. Pass root vars to included Taskfiles in the `includes:` entry (`vars: { PY: "{{.PY}}" }`); inheritance is unreliable.
4. Prefix top-level vars of included Taskfiles with the namespace (`RUST_RUN`, not `RUN`); they share one scope and the last loaded wins. `task --verbose --dry <name>` shows the rendered command.
5. Treat `{{.TASKFILE_DIR}}` as the including file's directory; never append the repository path to it.
6. Write paths relative to the repository root; commands run there.
7. Never set `PATH` in `env:`; the runner ignores it, even static. Resolve user-installed binaries instead:

   ```yaml
   vars:
     TOOL:
       sh: command -v tool 2>/dev/null || printf '%s' "${PIPX_BIN_DIR:-$HOME/.local/bin}/tool"
   ```

8. Run locked dev-group tools through the locked environment runner; they need no resolving.
9. Use `rm` then `mv`, never `mv -f`; shimmed coreutils on some machines fail on it.
10. Gate every task that deletes data with a `preconditions` check on `CONFIRM=yes` and a matching deny rule in `.claude/settings.json`.
