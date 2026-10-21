# Copilot instructions

Place in a pillar at `.github/copilot-instructions.md`.

Project rules live in [CLAUDE.md](../CLAUDE.md). Read it before changing anything. Shared
directives: https://github.com/Levia-Labs/Crepidoma/tree/main/plugins/crepidoma/directives

This file is a pointer, not a second copy. Essentials:

1. Taskfile is the interface. Discover tasks with `task --list`.
2. Run `task quality:gate` before declaring work done.
3. One command per call. No chaining.
4. Bash only.
5. `python3` on Linux, `python` on Windows.
6. Never commit secrets.
7. Commits follow Conventional Commits.
