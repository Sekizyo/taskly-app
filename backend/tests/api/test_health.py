from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.api.dependencies import get_repository
from app.api.health import router


@pytest.fixture
def health_repository():
    return Mock()


@pytest.fixture
def health_client(health_repository):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_repository] = lambda: health_repository
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def test_health_reports_ok_after_querying_the_database(health_client, health_repository):
    response = health_client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    statement = health_repository.session.execute.call_args.args[0]
    assert "FROM todos" in str(statement)
    assert "LIMIT" in str(statement)


def test_health_fails_when_the_database_is_unreachable(health_client, health_repository):
    health_repository.session.execute.side_effect = OperationalError("SELECT 1", {}, Exception("down"))
    assert health_client.get("/api/health").status_code == 500
