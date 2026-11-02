from unittest.mock import Mock

from sqlalchemy.orm import Session

from app.core import database
from app.core.database import create_database_engine, create_session_factory, initialize
from app.features.todos.models import Base


def test_engine_enables_pre_ping_and_a_connect_timeout(monkeypatch):
    create_engine = Mock(name="create_engine")
    monkeypatch.setattr(database, "create_engine", create_engine)
    assert create_database_engine("postgresql+psycopg://h/db") is create_engine.return_value
    create_engine.assert_called_once_with(
        "postgresql+psycopg://h/db", pool_pre_ping=True, connect_args={"connect_timeout": 10},
    )


def test_session_factory_binds_engine_and_keeps_objects_loaded_after_commit():
    engine = create_database_engine("postgresql+psycopg://taskly:taskly@localhost:5432/taskly")
    try:
        factory = create_session_factory(engine)
        assert factory.kw["bind"] is engine
        assert factory.kw["expire_on_commit"] is False
        assert issubclass(factory.class_, Session)
    finally:
        engine.dispose()


def test_initialize_creates_all_tables_on_the_engine(monkeypatch):
    create_all = Mock()
    monkeypatch.setattr(Base.metadata, "create_all", create_all)
    engine = Mock()
    initialize(engine)
    create_all.assert_called_once_with(engine)


def test_engine_uses_the_postgresql_psycopg_driver():
    url = "postgresql+psycopg://taskly:taskly@localhost:5432/taskly"
    engine = create_database_engine(url)
    try:
        assert engine.url.drivername == "postgresql+psycopg"
        assert engine.dialect.name == "postgresql"
        assert engine.dialect.driver == "psycopg"
        assert engine.url.database == "taskly"
    finally:
        engine.dispose()
