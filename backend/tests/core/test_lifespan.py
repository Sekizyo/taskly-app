import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.core import lifespan as lifespan_module
from app.core.lifespan import lifespan


@pytest.fixture
def database(monkeypatch):
    engine = Mock(name="engine")
    fakes = SimpleNamespace(
        engine=engine,
        create_database_engine=Mock(return_value=engine),
        initialize=Mock(),
        create_session_factory=Mock(return_value="session-factory"),
    )
    for name in ("create_database_engine", "initialize", "create_session_factory"):
        monkeypatch.setattr(lifespan_module, name, getattr(fakes, name))
    return fakes


def make_app():
    return SimpleNamespace(state=SimpleNamespace(database_url="postgresql+psycopg://u:p@h/db"))


def run(app, body=lambda app: None):
    async def scenario():
        async with lifespan(app):
            body(app)
    asyncio.run(scenario())


def test_startup_initializes_schema_and_exposes_session_factory(database):
    app = make_app()
    seen = []
    run(app, lambda app: seen.append(app.state.session_factory))
    database.create_database_engine.assert_called_once_with("postgresql+psycopg://u:p@h/db")
    database.initialize.assert_called_once_with(database.engine)
    database.create_session_factory.assert_called_once_with(database.engine)
    assert seen == ["session-factory"]
    database.engine.dispose.assert_called_once_with()


def test_engine_is_disposed_when_initialization_fails(database):
    database.initialize.side_effect = RuntimeError("database unavailable")
    app = make_app()
    with pytest.raises(RuntimeError, match="database unavailable"):
        run(app)
    database.create_session_factory.assert_not_called()
    assert not hasattr(app.state, "session_factory")
    database.engine.dispose.assert_called_once_with()


def test_engine_is_disposed_when_the_application_fails(database):
    def fail(app):
        raise ValueError("request crashed")
    with pytest.raises(ValueError, match="request crashed"):
        run(make_app(), fail)
    database.engine.dispose.assert_called_once_with()
