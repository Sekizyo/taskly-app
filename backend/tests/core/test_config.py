import pytest

from app.core import config
from app.core.config import resolve_database_url

DB_ENV = {
    "POSTGRES_USER": "taskly",
    "POSTGRES_PASSWORD": "p@ss/word",
    "POSTGRES_HOST": "db.internal",
    "DB_PORT": "6543",
    "POSTGRES_DB": "tasks",
}


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch):
    # Never let a developer's .env or shell leak into these tests.
    monkeypatch.setattr(config, "load_dotenv", lambda *args, **kwargs: None)
    for name in ["DATABASE_URL", *DB_ENV]:
        monkeypatch.delenv(name, raising=False)


def test_explicit_url_takes_precedence_over_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://env/db")
    assert resolve_database_url("sqlite:///explicit.db") == "sqlite:///explicit.db"


def test_database_url_environment_variable_is_used_when_set(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://env/db")
    for name, value in DB_ENV.items():
        monkeypatch.setenv(name, value)
    assert resolve_database_url() == "postgresql+psycopg://env/db"


def test_builds_url_from_postgres_variables_and_escapes_the_password(monkeypatch):
    for name, value in DB_ENV.items():
        monkeypatch.setenv(name, value)
    assert resolve_database_url() == "postgresql+psycopg://taskly:p%40ss%2Fword@db.internal:6543/tasks"


def test_missing_postgres_variable_raises_key_error(monkeypatch):
    for name, value in DB_ENV.items():
        if name != "POSTGRES_HOST":
            monkeypatch.setenv(name, value)
    with pytest.raises(KeyError, match="POSTGRES_HOST"):
        resolve_database_url()


def test_loads_dotenv_from_repository_root_without_overriding(monkeypatch):
    calls = []
    monkeypatch.setattr(config, "load_dotenv", lambda path, override: calls.append((path, override)))
    resolve_database_url("sqlite://")
    (path, override), = calls
    assert path.name == ".env"
    assert (path.parent / "backend" / "app" / "core" / "config.py").exists()
    assert override is False
