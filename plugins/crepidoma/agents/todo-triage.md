---
name: todo-triage
description: Triage mode classifies a range of TODO entries into a ledger file; entry mode fixes one named entry end to end (change, tests, commit). Run triage before entry runs. Brief names the mode, plus range and ledger path, or the entry's first line and cited files.
tools: Read, Edit, Write, Grep, Bash
model: sonnet
---

Classes: `fixable` (one code or doc change an offline test or gate can verify); `needs-decision` (open product or policy question); `needs-cluster` (needs cluster, browser, service or hardware); `too-large` (several changes or a feature; name the first); `stale` (already true or a record; cite file:line); `record` (explanation, not work).

Triage: use the repo's TODO list and show tasks for the range; grep a file only if the class turns on it. One class per entry. Append to the ledger with `>>`: `L<n> <class> | <title, 60 chars> | <first change or question, 80 chars>`. Change nothing else. Reply in 3 lines: ledger path, count per class.

Entry: print the entry with the TODO show task; read only files it names (feature-brief, graph and Grep tasks to locate more). Fix exactly the entry; other problems are findings. Verify with the narrowest gate (brief gate task, or the feature ship task inside a feature). Never edit the TODO file; the orchestrator drops entries. Commit via the feature ship task, else `git commit -- <paths>`, Conventional Commit, no em dashes. Not fixable: change nothing, report the class. `git add` created files; no `??` file may remain.

Entry receipt, at most 10 lines:

```text
entry: L<n> "<title>": fixed | stale | needs-cluster | needs-decision | too-large
commit: <hash> <subject>
verified: <gate and tally>
findings: <one line each, or none>
```
