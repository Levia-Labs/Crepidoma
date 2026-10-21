# Shell and safety

1. Bash only; PowerShell is denied. One command per call: no `cd`, no `&&` chains of unrelated steps; pass paths instead.
2. rtk rewrites commands; use `rtk proxy <cmd>` when exact output matters, never escape heredocs for it.
3. Widen permissions only on an explicit request. Never add allow rules for interpreters or wrappers (`python3 *`, `xargs *`, `find *`).
4. Turn every convention into an ast-grep or lint rule with valid and invalid fixtures, no initial exceptions. A defect seen twice becomes a rule.
5. Verify locally first; CI repeats the local gate, never replaces it.
6. Confirm before any irreversible publish or delete; pruning is opt-in.
7. Tests never write real user data or call real services.
8. Findings outside the current job go to TODO via `task todo:add`, not into the diff.
