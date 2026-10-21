# 0005. Ratcheting baselines

## Status

Accepted, 2026-10-20. Supersedes the per-pillar ADRs on this topic.

## Context

Quality gates are often introduced into a tree that already fails them: files past the length
limit, documents naming paths that do not resolve, type errors, coverage below target,
duplicated code. Turned on strictly, such a gate fails on day one, and the usual outcomes are
that it is disabled or bypassed with `--no-verify`. Turned on as a warning, it is ignored and
the count grows. Neither outcome improves the code.

A ratchet accepts what exists today, fails anything new, and lets the accepted set only shrink.

## Decision

1. Every gate that measures an already imperfect property compares against a committed
   baseline. The shared tool `crepidoma-ratchet` implements the comparison.
2. Baseline files live under `.ratchet/`, one file per gate, committed with the code.
3. Finding gates keep a per-item list, never a single global count, so a fix in one place
   cannot pay for a regression in another. A finding in the baseline passes; a finding not in
   it fails.
4. `crepidoma-ratchet long-files` fails any file past 300 lines that is not in the baseline. A
   baselined file may shrink or hold, never grow.
5. `crepidoma-ratchet metric` ratchets a numeric value in one declared direction: `up` for
   metrics that must not fall, such as branch coverage; `down` for metrics that must not rise,
   such as duplication or type-error count.
6. A new project, or a gate whose tree already passes, starts with an empty baseline.
7. There are no blanket exclusions. Generated or vendored files that exceed a limit are listed
   in the baseline individually, where review can see them.
8. Regenerating a baseline is a separate, deliberate task that appears in the diff as its own
   change. It records progress; it is never a way to make a failing build pass.
9. A check reports how many findings were fixed since the baseline was written and directs the
   reader to tighten the baseline.
10. Where a tool ships a native baseline that shrinks itself as findings are fixed, the native
    baseline is used and stored under `.ratchet/`.

## Consequences

1. A gate is turned on and stays on, from a tree that did not pass it. Nobody has to clear the
   backlog before the gate has value.
2. Quality moves one direction. A regression fails at the commit that introduced it, which is
   the moment its author still knows what was meant.
3. A baseline can technically be regenerated to accept more findings. The barrier is review:
   the change shows up as a diff that says "accept more findings".
4. Baseline files must be kept current. A stale baseline, with fixed findings not removed,
   makes the gate weaker than it could be.
5. Listing generated files individually costs baseline churn when generated output changes,
   in exchange for no file escaping the limit unseen.
