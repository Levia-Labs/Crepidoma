---
name: python-patterns
description: Use when writing or reviewing Python 3.12+ code - type hints, error handling, dataclasses, context managers, concurrency, project layout and uv tooling.
---

<!-- Adapted from affaan-m/ECC skills/python-patterns/SKILL.md @ 30b68924ae9729159f44326aa3134b1d9d67c0e2, MIT, see THIRD_PARTY_NOTICES.md -->

# Python patterns

Target Python 3.12+, stdlib first, uv for dependencies, `ruff` for lint and format, `mypy` or `pyright` for types, pytest for tests. Run each through the repo's tasks when they exist.

## Principles

1. Explicit over implicit: pass configuration in, avoid import-time side effects and hidden globals.
2. EAFP: try the operation and catch the specific exception; check first only when the check is cheap and the failure costly.
3. Small functions with one job; return early to flatten nesting.
4. Pure functions at the core, I/O at the edges.

## Types

```python
type Handler = Callable[[Request], Response]  # 3.12 alias syntax


def first[T](items: Sequence[T]) -> T | None:  # 3.12 generics
    return items[0] if items else None
```

1. Built-in generics (`list[str]`, `dict[str, int]`), `X | None`, never `Optional` or `typing.List`.
2. Annotate every public function and method; annotate returns of `__init__` as `None` only when it has no typed args.
3. `Protocol` for structural typing at module boundaries instead of base classes.
4. `TypedDict` for JSON-shaped dicts, `Literal` and `Enum` for closed sets, `Final` for constants, `@override` on overrides.
5. Avoid `Any`; when unavoidable, narrow at the first opportunity.
6. No `# type: ignore` without a code and a reason.

## Errors

1. Catch the narrowest exception; never bare `except:` and never `except Exception: pass`.
2. Chain causes: `raise ConfigError("bad port") from exc`; use `raise ... from None` only to hide a noisy cause on purpose.
3. One base exception per package, specific subclasses below it; carry data as attributes, not only in the message.
4. Use `ExceptionGroup` and `except*` for concurrent task failures.
5. Log with `logging` at the boundary that handles the error, once; do not log and re-raise.
6. Validate at trust boundaries (CLI args, files, network, env) and fail fast with a clear message.

## Resources

1. `with` for every file, lock, connection and temporary resource; `pathlib.Path` for paths.
2. `contextlib.contextmanager` for a one-off, a class with `__enter__`/`__exit__` when it carries state; `ExitStack` for a dynamic number of resources.
3. Open text files with an explicit `encoding="utf-8"`.
4. Paths from outside: `resolved = (root / name).resolve()` then `resolved.is_relative_to(root.resolve())`.

## Data

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class Job:
    name: str
    retries: int = 3
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.retries < 0:
            raise ValueError("retries must be >= 0")
```

1. `dataclass(frozen=True, slots=True)` by default; `field(default_factory=list)` for mutable defaults.
2. `NamedTuple` for small immutable records that unpack; `dict` only for dynamic keys.
3. Parse into typed objects once at the boundary; pass the objects, not raw dicts.

## Iteration

1. Comprehensions for a single transform or filter; a generator function once it needs two clauses and a condition.
2. Generator expressions inside `sum`, `any`, `all`, `"".join` to avoid intermediate lists.
3. `itertools.batched`, `pairwise`, `chain.from_iterable`; `enumerate` and `zip(strict=True)` instead of index loops.
4. `"".join(parts)` or `io.StringIO` to build strings in loops.
5. Stream large files line by line; never `read()` an unbounded input.

## Decorators

1. Always `functools.wraps`; type with `ParamSpec` and `TypeVar` so signatures survive.
2. `functools.cache` or `lru_cache(maxsize=...)` only on pure functions with hashable args; never on methods that hold instances alive.
3. Keep decorators single-purpose (timing, retry, caching); do not hide control flow in them.

## Concurrency

1. I/O-bound: `asyncio` with `asyncio.TaskGroup` and `asyncio.timeout`, or `ThreadPoolExecutor` for blocking libraries.
2. CPU-bound: `ProcessPoolExecutor`; check the free-threaded build before assuming threads stay GIL-bound.
3. Never call blocking I/O or `time.sleep` inside a coroutine; use `asyncio.to_thread`.
4. Hold a `threading.Lock` around shared mutable state; prefer message passing (`queue.Queue`, `asyncio.Queue`).
5. Cancel and await every task you create; no fire-and-forget without a stored reference.

## Layout and imports

```text
src/pkg/__init__.py
src/pkg/core.py
tests/test_core.py
pyproject.toml
uv.lock
```

1. Src layout (the package under a `src` folder), one `pyproject.toml`, `uv.lock` committed.
2. Import order stdlib, third party, local; ruff's `I` rules enforce it. No `import *`; no circular imports (move shared types to a leaf module).
3. Export the public API in `__init__.py` with `__all__`.
4. Scripts: `if __name__ == "__main__": raise SystemExit(main())` with `main(argv: list[str] | None = None) -> int`.

## Performance

1. Measure first (`cProfile`, `timeit`); fix algorithms before micro-optimizing.
2. `__slots__` (or `slots=True`) for many small objects.
3. `set` or `dict` for membership tests in loops; `collections.deque` for queues; `bisect` for sorted data.
4. Hoist invariant work out of loops; avoid N+1 queries by batching.

## Tooling

```bash
uv sync                      # install from lock
uv run ruff format .         # format
uv run ruff check . --fix    # lint
uv run mypy src              # types
uv run pytest                # tests
uv run bandit -r src         # security scan
uv add <pkg>                 # add a dependency
```

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "S", "SIM", "RUF"]

[tool.mypy]
strict = true
```

## Anti-patterns

| Avoid                                | Use                                                                  |
| ------------------------------------ | -------------------------------------------------------------------- |
| `def f(x=[])`                        | `def f(x=None)` then create inside, or `field(default_factory=list)` |
| `type(x) == T`                       | `isinstance(x, T)`                                                   |
| `x == None`                          | `x is None`                                                          |
| `except:`                            | `except SpecificError:`                                              |
| `from m import *`                    | explicit imports                                                     |
| `os.path.join` chains                | `pathlib.Path`                                                       |
| `subprocess.run(cmd, shell=True)`    | `subprocess.run([...], check=True)`                                  |
| `yaml.load`, `pickle.loads` on input | `yaml.safe_load`, JSON                                               |
| `print` in library code              | `logging.getLogger(__name__)`                                        |
| `open(p)` without `with`             | `with open(p, encoding="utf-8") as f:`                               |
| mutable module-level state           | pass state in, or a frozen dataclass                                 |
