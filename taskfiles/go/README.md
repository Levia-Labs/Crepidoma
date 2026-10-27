# Go

- Vet, test, format, fuzz and race-test one Go module; set GO_DIR when including.

Include with the module directory:

```yaml
includes:
  go:
    taskfile: .crepidoma/taskfiles/go
    vars: { GO_DIR: indexer }
```

- `task go:check` runs `go vet` and `go test`, prints the ok-package count and only failure lines; the full output stays in a log whose path is printed on failure.
- `task go:fmt` runs `gofmt -l -w`, exits 1 listing rewritten files.
- `task go:fuzz FUZZTIME=10s` runs each Fuzz target for FUZZTIME (a Go duration) with `-parallel 1`.
- `task go:race` runs `go test -race`; skipped with exit 0 when CGO or a C compiler is missing.
- Pre-commit hooks `go-check` and `go-fmt` come from `.pre-commit-hooks.yaml`.

## Contents

<!-- contents:start -->

- [`Taskfile.yml`](Taskfile.yml) - Task namespace with 4 tasks.

<!-- contents:end -->
