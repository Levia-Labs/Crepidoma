# Writing a Crepidoma tool

Every script that agents or tasks call follows these rules, so a model turn stays a tool call
with a small receipt.

1. Location: `plugins/crepidoma/scripts/<name>.py`; test: `plugins/crepidoma/tests/test_<name>.py`.
   Pytest imports the script by module name (`import <name>`); `pythonpath` already includes the
   scripts directory.
2. Python 3.12+, standard library only. Entry point `def main(argv: list[str] | None = None) -> int`
   with argparse subcommands; module docstring starts with a one-line summary and a `Usage:` line.
3. Output is the minimum the next decision needs: pass/fail, counts, ids, failing lines. Default
   output never exceeds 20 lines or 1 KB; `--report FILE` writes full detail. `--json` where a
   caller parses the result.
4. Exit codes: 0 ok, 1 finding or failure, 2 usage error, 3 "wait" or "not now" where the tool
   gates work.
5. Paths come from arguments or are computed from `Path.cwd()` / `CLAUDE_PROJECT_DIR`; never
   absolute, never a repo or person name. Read text with `encoding="utf-8"`; write with
   `newline="\n"`.
6. Hook state lives in `hooks.state_dir(ROOT)` (the git dir, else a per-user cache), never a
   shared temp dir.
7. Tests use `tmp_path`, `monkeypatch` and `capsys`; no network, no real home directory, no real
   transcripts. Build any fixture that looks like a secret, email or local path by concatenation.
8. Taskfile entries live in `taskfiles/<namespace>/Taskfile.yml`, call
   `uv run --no-project --python ">=3.12" "{{.TASKFILE_DIR}}/../../plugins/crepidoma/scripts/<name>.py"`
   (a command name such as `python3` can resolve to another interpreter), carry a `desc`
   with a `Usage:` hint, and run in `{{.USER_WORKING_DIR}}`.
