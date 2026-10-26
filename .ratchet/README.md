# .ratchet

- Ratchet baselines; numbers only move in the good direction.
- Bandit skips the vendored `.crepidoma` submodule; a consumer's `bandit.baseline` may now be higher than the real count. Lower it to the new count.

## Contents

<!-- contents:start -->

- [`bandit.baseline`](bandit.baseline) - Bandit finding count.
- [`coverage.baseline`](coverage.baseline) - Branch coverage percent.
- [`docs.baseline`](docs.baseline) - Accepted docs-gate findings.
- [`duplication.baseline`](duplication.baseline) - Ratchet baseline.
- [`long-files.baseline`](long-files.baseline) - Files allowed over 300 lines and their current length.
- [`types.baseline`](types.baseline) - Type checker error count.

<!-- contents:end -->
