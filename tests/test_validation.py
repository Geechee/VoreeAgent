"""Tests for input validation and security hardening."""
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    with patch("db.engine") as mock_engine, \
         patch("db.SessionLocal") as mock_session_factory, \
         patch("db.init_db"):
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)
        from main import app
        from auth import require_key
        app.dependency_overrides[require_key] = lambda: MagicMock()
        with TestClient(app) as c:
            yield c
        app.dependency_overrides.pop(require_key, None)


def _auth_headers():
    return {"Content-Type": "application/json"}


def test_empty_task_rejected(client):
    response = client.post("/api/task", json={"task": ""}, headers=_auth_headers())
    assert response.status_code == 422


def test_oversized_task_rejected(client):
    response = client.post("/api/task", json={"task": "x" * 10001}, headers=_auth_headers())
    assert response.status_code == 422


def test_empty_memory_rejected(client):
    response = client.post("/api/memories", json={"content": ""}, headers=_auth_headers())
    assert response.status_code == 422


def test_search_k_too_large_rejected(client):
    response = client.post("/api/memories/search", json={"query": "test", "k": 100}, headers=_auth_headers())
    assert response.status_code == 422


def test_search_k_zero_rejected(client):
    response = client.post("/api/memories/search", json={"query": "test", "k": 0}, headers=_auth_headers())
    assert response.status_code == 422


def test_empty_session_message_rejected(client):
    response = client.post("/api/sessions", json={"message": ""}, headers=_auth_headers())
    assert response.status_code == 422


def test_chain_too_few_roles_rejected(client):
    response = client.post("/api/chain", json={"task": "test", "roles": ["researcher"]}, headers=_auth_headers())
    assert response.status_code == 422


def test_invalid_plugin_method_rejected(client):
    response = client.post("/api/plugins", json={
        "name": "test", "description": "test", "url": "https://example.com",
        "method": "DELETE", "parameters": {}
    }, headers=_auth_headers())
    assert response.status_code == 422


def test_invalid_persona_name_rejected(client):
    response = client.post("/api/personas", json={
        "name": "Bad Name!", "display_name": "Test", "description": "Test",
        "system_prompt": "You are a test persona."
    }, headers=_auth_headers())
    assert response.status_code == 422


def test_rate_limit_too_high_rejected(client):
    response = client.post("/api/keys/bootstrap", json={"name": "test", "rate_limit": 99999}, headers=_auth_headers())
    assert response.status_code == 422


def test_security_headers_present(client):
    with patch("main.check_connection", return_value=True):
        response = client.get("/health")
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert response.headers.get("X-XSS-Protection") == "1; mode=block"
