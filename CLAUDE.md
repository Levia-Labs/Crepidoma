# Crepidoma

Foundation repo for Levia Labs pillars: plugin, task namespaces, configs, templates, ADRs.

- Public on GitHub: never commit local paths, emails, tokens or private repo names.
- Stack: Python 3.12+ stdlib, uv, pytest, Task, pre-commit.
- Every folder keeps a README (`task docs:readmes`).
- Ship through a PR, squash-merged; `main` is the only long-lived branch.
- Release: `task release -- X.Y.Z`, then `claude plugin marketplace update levia-labs`.
- `task validate` runs everything CI runs.
