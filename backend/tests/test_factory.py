from contextlib import asynccontextmanager

from fastapi.testclient import TestClient

from app import factory


def test_create_app_wires_database_url_and_routes(monkeypatch):
    monkeypatch.setattr(factory, "resolve_database_url", lambda url: f"resolved:{url}")
    app = factory.create_app("sqlite://")
    assert app.title == "Taskly API"
    assert app.state.database_url == "resolved:sqlite://"
    paths = app.openapi()["paths"]
    assert {path: sorted(operations) for path, operations in paths.items()} == {
        "/api/health": ["get"],
        "/api/todos": ["get", "post"],
        "/api/todos/{todo_id}": ["delete", "get", "patch"],
    }


def test_create_app_runs_the_database_lifespan_on_startup_and_shutdown(monkeypatch):
    events = []

    @asynccontextmanager
    async def fake_lifespan(app):
        events.append(("startup", app.state.database_url))
        yield
        events.append(("shutdown", app.state.database_url))

    monkeypatch.setattr(factory, "lifespan", fake_lifespan)
    monkeypatch.setattr(factory, "resolve_database_url", lambda url: "postgresql+psycopg://x")
    with TestClient(factory.create_app()):
        assert events == [("startup", "postgresql+psycopg://x")]
    assert events[-1] == ("shutdown", "postgresql+psycopg://x")


def test_create_app_without_url_defers_to_environment_resolution(monkeypatch):
    calls = []
    monkeypatch.setattr(factory, "resolve_database_url", lambda url: calls.append(url) or "postgresql+psycopg://x")
    factory.create_app()
    assert calls == [None]
