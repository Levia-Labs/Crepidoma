---
name: python-testing
description: Use when writing or reviewing pytest tests in a Python 3.12+ uv project - fixtures, parametrization, mocking, async tests, markers and configuration.
---

<!-- Adapted from affaan-m/ECC skills/python-testing/SKILL.md @ 30b68924ae9729159f44326aa3134b1d9d67c0e2, MIT, see THIRD_PARTY_NOTICES.md -->

# Python testing

pytest only, run through `uv run pytest` or the repo's test task. Run one file or the failed tests while iterating; the whole suite runs once at the end.

## Loop

1. Write a failing test for the behaviour; run it and confirm it fails for the right reason.
2. Write the minimal code that passes.
3. Refactor with the tests green.

A new pure function at a trust boundary (paths, names, URLs, parsers) also gets a property-based test with `hypothesis`.

## Structure

1. `tests/` mirrors the package: `tests/test_<module>.py`; shared fixtures in the `conftest.py` beside them.
2. One behaviour per test; the name states it: `test_parse_rejects_empty_input`.
3. Arrange, act, assert; no logic (loops, conditionals) in the test body.
4. Prefer plain functions; use a class only to share a fixture scope.
5. Assert on behaviour and outputs, not on private attributes or call order unless the order is the contract.

## Assertions

```python
with pytest.raises(ValueError, match="must be positive") as info:
    parse(-1)
assert info.value.args[0] == "must be positive"

assert result == pytest.approx(0.3, rel=1e-9)  # floats
assert {"a", "b"} <= set(result)  # subset, order-free
```

Use `pytest.raises` with `match`; never a bare `try/except` plus `assert False`.

## Fixtures

1. Default scope is function; widen to `module` or `session` only for read-only or expensive objects.
2. Teardown with `yield`; code after `yield` runs even when the test fails.
3. Prefer built-ins: `tmp_path` (not `tmpdir`), `monkeypatch`, `capsys`, `caplog`, `tmp_path_factory`.
4. `autouse=True` only for isolation that every test needs, such as clearing a cache or an environment variable.
5. A fixture returning a factory function beats many near-identical fixtures.

```python
@pytest.fixture
def make_user():
    created = []

    def _make(name="ada", **extra):
        user = User(name=name, **extra)
        created.append(user)
        return user

    yield _make
    for user in created:
        user.close()
```

## Parametrization

```python
@pytest.mark.parametrize(
    ("raw", "expected"),
    [("1", 1), (" 2 ", 2), pytest.param("x", None, id="not-a-number")],
)
def test_to_int(raw, expected):
    assert to_int(raw) == expected
```

1. Give non-obvious cases an `id`.
2. Stack decorators for a cross product; use `indirect=True` to feed a value into a fixture.
3. Mark known failures `pytest.param(..., marks=pytest.mark.xfail(strict=True, reason="..."))`.

## Mocking

1. Mock at the boundary you own (HTTP client, clock, subprocess, filesystem), never the unit under test.
2. Patch where the name is looked up, not where it is defined: `patch("app.service.requests.get")`.
3. Always `autospec=True` (or `create_autospec`) so a signature change fails the test.
4. Prefer `monkeypatch.setattr` and `monkeypatch.setenv` for simple replacement; they undo themselves.
5. Prefer a small fake class over a deep `MagicMock` chain.
6. `side_effect=[a, b, SomeError()]` scripts a sequence; `mock.assert_called_once_with(...)` checks the call.

```python
def test_fetch_retries(monkeypatch):
    calls = iter([TimeoutError(), {"ok": True}])

    def fake_get(url, timeout):
        value = next(calls)
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr("app.client.get", fake_get)
    assert fetch("u") == {"ok": True}
```

## Async

1. `pytest-asyncio` with `asyncio_mode = "auto"` in `pyproject.toml`, or mark each test `@pytest.mark.asyncio`.
2. Async fixtures use `@pytest_asyncio.fixture` in strict mode.
3. Mock coroutines with `AsyncMock`; assert with `assert_awaited_once_with`.
4. Bound waits with `asyncio.timeout(...)`; a hung test must fail, not stall the suite.

## Files and time

1. Write only under `tmp_path`; never the working tree or a user directory.
2. Freeze time by injecting a clock or using `time-machine`; never `sleep` to wait for a condition.
3. Seed randomness; print the seed on failure.

## Markers and selection

Declare every marker, and fail on typos:

```toml
[tool.pytest.ini_options]
minversion = "8.0"
testpaths = ["tests"]
addopts = "-ra --strict-markers --strict-config"
markers = [
  "slow: takes more than a second",
  "integration: touches network, database or subprocess",
]
```

1. `uv run pytest -m "not slow and not integration"` for the fast loop.
2. `-x` stops at the first failure, `--lf` reruns the last failures, `-k "expr"` selects by name, `--pdb` drops into the debugger.
3. `-p no:cacheprovider` in read-only CI.

## Coverage

1. `uv run pytest --cov=<package> --cov-report=term-missing --cov-branch`.
2. Gate with `--cov-fail-under=N` and ratchet N up, never down.
3. Coverage finds untested lines; it does not prove assertions are meaningful. Review the assertions.

## Database and API tests

1. Wrap each DB test in a transaction rolled back at teardown, or use an in-memory database; never share state between tests.
2. Drive web apps through their test client (`fastapi.testclient.TestClient`, Flask `app.test_client()`) and assert status code, body and headers; override dependencies instead of patching internals.
3. Test the error paths of every endpoint: invalid input, missing auth, foreign record.

## Do not

1. Depend on test order or on state left by another test.
2. Test implementation details that a refactor would change.
3. Catch exceptions inside a test to make it pass.
4. Leave `print` or `breakpoint()` in a test.
5. Regenerate a snapshot or baseline to make a failing test pass.
6. Write a test that passes without the code under test; check by breaking the code once.
