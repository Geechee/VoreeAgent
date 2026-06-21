"""Tests for API endpoints using FastAPI test client."""
from unittest.mock import patch, MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client with mocked database."""
    with patch("db.engine") as mock_engine, \
         patch("db.SessionLocal") as mock_session_factory, \
         patch("db.init_db"):

        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value = None

        from main import app
        with TestClient(app) as c:
            yield c


def test_health_no_auth_required(client):
    """Health endpoint should work without an API key."""
    with patch("main.check_connection", return_value=True):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


def test_dashboard_no_auth_required(client):
    """Dashboard should serve without an API key."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_tasks_requires_auth(client):
    """API endpoints should require X-API-Key header."""
    response = client.get("/api/tasks")
    assert response.status_code == 401
    assert "Missing X-API-Key" in response.json()["detail"]


def test_memories_requires_auth(client):
    response = client.get("/api/memories")
    assert response.status_code == 401


def test_sessions_requires_auth(client):
    response = client.get("/api/sessions")
    assert response.status_code == 401


def test_invalid_key_rejected(client):
    from auth import require_key
    from main import app

    def fake_require_key():
        raise HTTPException(status_code=403, detail="Invalid or revoked API key")

    app.dependency_overrides[require_key] = fake_require_key
    response = client.get("/api/tasks")
    assert response.status_code == 403
    app.dependency_overrides.pop(require_key, None)
