# 0006. Testing strategy

## Status

Accepted, 2026-10-20. Supersedes the per-pillar ADRs on this topic.

## Context

The riskiest code in a project usually sits next to I/O: provisioning against a
live service, proxying to an upstream, writing to a database. The common excuse
is that such code cannot be tested without credentials, a network and running
containers. A suite with those prerequisites is a suite nobody runs, so the
dangerous behaviour goes unpinned and a configuration typo reaches production.

At the same time, some rules can only be stated in the real backend, such as a
database constraint that other engines silently ignore. A constraint that only
exists in production is a constraint nothing tests.

Tests kept far from the code they cover also make review and deletion harder:
reviewing a feature means opening two unrelated parts of the repository, and
removing one becomes a two-place edit.

## Decision

1. The default test gate runs offline. No containers, no network, no tokens, no
   credentials. It passes from a clean clone with only the declared development
   dependencies installed.
2. Risky logic is kept away from I/O. Planning, validation, normalisation and
   guard logic live in pure modules with no I/O and no SDK imports, and are
   tested directly, covering every normalisation rule and every guard.
3. The thin I/O layer is tested against fakes that behave like the real library.
   Fakes are constrained to the real type's interface (spec'd mocks), so type
   checks and attribute access behave as they would against real objects, and
   the calls that would have been made are recorded and asserted.
4. Outbound HTTP is intercepted at the transport layer, not by replacing the
   client. The real client code (URLs, headers, payloads, error translation) is
   exercised without an upstream. Upstream errors are asserted to map to the
   intended status codes.
5. Third-party libraries are never monkeypatched at import time.
6. Request handlers and routes are tested through the framework's test client,
   with downstream handlers replaced by recorders. Tests cover dispatch,
   capability filtering, partial failure and the mapping to status codes.
7. Committed configuration is validated by the suite against its schemas, and
   repository-wide invariants are asserted: referenced names exist, values are
   supported, names are unique, no secrets are committed, and unsafe flags
   (destructive pruning, leftover dry-run) are not left on.
8. Tests are isolated from the working tree. Any test that writes files points
   the relevant directory at a temporary location through a fixture. A suite
   that must read real repository content does so explicitly and read-only.
9. Tests live beside the code they cover. A feature's tests sit in that
   feature's own test package, created empty when the feature is scaffolded. A
   shared top-level suite holds only what belongs to no feature: discovery,
   registration, routing and settings.
10. Environment that settings read at import time is set in the test runner's
    configuration, not in a fixture, because the framework may initialise before
    any fixture module is loaded. Shared fixtures live at the root so that every
    nested suite inherits them.
11. Behaviour that only the production backend can enforce is covered by a
    second run of the same suite against that real backend, started in a
    throwaway container behind its own task. Tests for such rules skip
    themselves, loudly, on any backend that cannot enforce them.
12. Browser-side code has its own offline test layer in the default gate,
    rendering every route inside the application's real providers. Tests in a
    real browser against a running stack sit behind their own task.
13. Suites that need containers, a running stack or credentials are not part of
    the default check task. They are opt-in, named tasks.
14. Tests assert the specific rule that matters, not a serialised snapshot,
    because a snapshot diff does not say which rule broke.
15. Discovery and glob-driven tests assert a minimum count as well as an exact
    match, so a pattern that silently matches nothing cannot make the remaining
    assertions vacuously true.
16. Drift against third-party libraries is tested, not assumed: tests rediscover
    the library's own tables or aliases and assert that the project's copies
    match.
17. Test dependencies are declared separately from runtime dependencies, so
    runtime images stay unchanged.

## Consequences

1. The test task runs from a clean clone with nothing else installed, and the
   default check gate never needs a network, containers or secrets.
2. Dangerous behaviour is pinned by tests that state intent: undeclared
   resources survive, only previously managed resources are pruned, a dry run
   saves nothing.
3. A typo in committed configuration fails the test task, not a live run.
4. Backend-specific constraints are exercised by the real-backend run instead of
   existing only in production. That run needs a container runtime and is not
   part of the default gate.
5. A feature folder is self-contained: code, tests, documentation. Deleting a
   feature deletes its tests.
6. Library upgrades that change behaviour the project depends on are caught by
   drift tests rather than discovered in production.
7. High-fidelity integration against real external services remains manual or
   opt-in; the offline suite does not replace it.
