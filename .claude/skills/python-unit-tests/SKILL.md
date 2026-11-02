---
name: python-unit-tests
description: Conventions and patterns for writing pytest unit tests for the Taskly FastAPI backend (backend/app) – fixtures, repository mocks, TestClient, SQLAlchemy without a database, env/config tests. Use whenever creating or updating tests under backend/tests.
---

# Backend unit tests (pytest)

Stack: Python 3.13, FastAPI, SQLAlchemy 2, Pydantic 2, pytest + pytest-cov. Tests live
in `backend/tests/`, mirroring `backend/app/`. Every test directory has an
`__init__.py`. Imports use the `app.` package (`pythonpath = ["."]` from `backend/`).

## Style (match the existing tests)

- Plain functions `test_<behaviour_in_words>()`; no classes. Name says the behaviour,
  e.g. `test_update_returns_404_when_task_is_missing`.
- Short tests, one behaviour each; `@pytest.mark.parametrize` for input tables.
- Assert on observable results *and* on interactions that matter
  (`assert_called_once_with`, `assert_not_called`).
- No sleeps, no real time/network/DB. Freeze time by asserting ranges or by patching
  `datetime` in the module under test only when needed.

## Reuse before you write

`backend/tests/conftest.py` provides:
- `repository_mock` – `create_autospec(TodoRepository, instance=True)` from
  `tests/mocks.py` (interface-checked: calling a non-existent method fails).
- `client` – `TestClient` over a bare `FastAPI()` with only the todos router mounted
  and `get_repository` overridden by `repository_mock`.
- `todo_values` (dict), `todo` (`Todo` schema), `model_factory` (dict → `TodoRecord`).

`conftest.py` and `tests/mocks.py` are human-owned: the PR workflow rejects patches that
touch `conftest.py`. Define extra fixtures locally in the test module instead.

## Patterns by layer

**Router (`features/*/router.py`)** – use `client` + `repository_mock`. Cover success
status + body (`todo.model_dump(mode="json")`), 404 branches, 422 path/body validation
(and that the repository was *not* called), 204 empty body.

**Repository (`features/*/repository.py`)** – unit test with `Mock(spec=Session)`;
assert the SQLAlchemy calls (`add`, `commit`, `refresh`, `delete`, `get`) and the
returned schema. For `refresh`, give the mock a `side_effect` that sets `id` on the
record so `from_model` can validate. Compare statements with `statement.compare(...)`.

**Dependencies (`api/dependencies.py`)** – drive the generator manually:
`gen = get_repository(request)`; `next(gen)`; then `gen.close()` (normal exit) or
`gen.throw(Exc)` (error path → `rollback` then `close`). Build `request` as
`Request({"type": "http", "app": SimpleNamespace(state=SimpleNamespace(session_factory=...))})`.

**Health / other routers needing `Repository`** – mount the router on a bare
`FastAPI()`, override `get_repository` with a `Mock()` exposing `.session`.

**Config (`core/config.py`)** – use `monkeypatch.setenv/delenv` and patch
`app.core.config.load_dotenv` so a developer's `.env` can never leak into a test.

**Lifespan / factory** – patch the collaborators in the module under test
(`app.core.lifespan.create_database_engine`, `initialize`, ...) and run the lifespan
with `async with lifespan(app):` inside `asyncio.run(...)` or via
`with TestClient(app):`. Assert `engine.dispose()` runs on success *and* on failure.
Never connect to Postgres: a `postgresql+psycopg://` URL is fine as long as nothing
connects (engines are lazy).

## Run

From the repository root:

```sh
scripts/agent/run_tests.sh backend .test-agent/run tests/path/test_x.py   # focused
scripts/agent/run_tests.sh backend .test-agent/run                         # full suite + coverage
```

Focused paths are relative to `backend/` (e.g. `tests/core/test_config.py`).
Coverage JSON is written to `.test-agent/run/backend-coverage.json`; check the
`missing_lines` of the files you targeted.
