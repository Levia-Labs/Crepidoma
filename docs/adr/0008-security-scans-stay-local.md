# 0008. Security scans stay local

## Status

Accepted, 2026-10-20.

## Context

A hardened workstation resolves only whitelisted hosts. semgrep's default configuration
fetches rule packs from its registry and sends metrics. A gate that needs the network fails
on that machine, and a failing gate gets skipped. Hosted scanners would also send source
and findings off the machine.

## Decision

1. Secret, SAST, workflow and dependency scans run locally through `task security:check`.
2. Scanners: gitleaks for secrets, semgrep for SAST with metrics and version checks off,
   zizmor for workflows, osv-scanner and pip-audit for dependencies.
3. semgrep runs only local rules, never registry packs.
4. CI repeats the same scans; a local pass does not replace the CI run.
5. Nothing leaves the machine except advisory database fetches by the dependency scanners.
6. A scanner absent on the editing host skips with one line; under CI it fails.

## Consequences

1. No community rule packs. Coverage is the local rules plus ruff `S` rules; adding a rule
   means writing one.
2. Dependency scans need network for advisory data. This is the only egress, and it carries
   package names and versions, not source.
3. Local and CI run the same scanners, so a CI-only failure signals an environment
   difference, not a different rule set.
4. A skipped scanner on the editing host leaves a gap until CI runs.
