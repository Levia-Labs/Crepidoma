---
name: migrate-pillar
description: Use when asked to migrate one or more pillar repos onto Crepidoma (replace copied agents, hooks, Taskfiles, configs and process ADRs with links). Orchestrates one pillar-migrator lane per repo, then pushes each branch and opens one PR per repo.
---

# Migrate pillars

The main thread orchestrates; `pillar-migrator` (Sonnet) does the edits. At most 6 lanes, one per pillar.

1. **Check.** Run `task claude:budget:check`; stop at the ceiling. For each pillar, `git -C <pillar> status --short` must be empty; skip and report dirty pillars.
2. **Branch.** For each pillar: `git -C <pillar> switch -c crepidoma-migration` from its default branch.
3. **Before.** From the Crepidoma checkout: `task drift -- <pillar>`; keep the final counts line.
4. **Dispatch.** One `pillar-migrator` per pillar with the pillar path, the branch name and the Crepidoma checkout path. Wait for every receipt.
5. **After.** `task drift -- <pillar>` again; expect `duplicate=0 drifted=0`. A pillar that still drifts gets one more lane with the drift report path, then is reported.
6. **Publish.** For each finished pillar: `git -C <pillar> push -u origin crepidoma-migration`, then `gh pr create` in that repo with the receipt as the body. Never merge. A pillar whose branch has no commits (`git -C <pillar> log --oneline main..crepidoma-migration` empty) gets no PR: run `task git:after-merge -- <pillar> crepidoma-migration` to return it to its default branch.
7. **Report.** One line per pillar: PR URL, drift before and after, gate result.
8. **After merge.** Once a pillar PR merges, run `task git:after-merge -- <pillar> crepidoma-migration` so the checkout leaves the migration branch.
