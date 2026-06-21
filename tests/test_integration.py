"""Integration tests — hit the real API with the test database.
These tests verify the full request/response cycle without mocking.
Requires: docker compose up -d (database must be running)
Run: docker compose run --rm app python -m pytest tests/test_integration.py -v
"""
import os
import pytest
from fastapi.testclient import TestClient

# Skip if no real database available
pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL", "").startswith("postgresql"),
    reason="Integration tests require a running PostgreSQL database",
)


@pytest.fixture(scope="module")
def client():
    from main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def api_key(client):
    """Bootstrap an API key, or create one using an existing key from the database."""
    resp = client.post("/api/keys/bootstrap", json={"name": "integration-test"})
    if resp.status_code == 201:
        return resp.json()["key"]
    # Keys exist — create via the DB directly
    from db import SessionLocal
    from auth import create_api_key
    db = SessionLocal()
    try:
        raw, _ = create_api_key(db, "integration-test")
        return raw
    finally:
        db.close()


@pytest.fixture(scope="module")
def headers(api_key):
    return {"X-API-Key": api_key, "Content-Type": "application/json"}


# ── Health & Dashboard ──

def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["database"] is True


def test_dashboard_serves_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "VOREE" in resp.text


def test_api_docs_available(client):
    resp = client.get("/docs")
    assert resp.status_code == 200


def test_redoc_available(client):
    resp = client.get("/redoc")
    assert resp.status_code == 200


# ── Auth ──

def test_no_key_returns_401(client):
    resp = client.get("/api/tasks")
    assert resp.status_code == 401


def test_bad_key_returns_403(client):
    resp = client.get("/api/tasks", headers={"X-API-Key": "invalid_key"})
    assert resp.status_code == 403


def test_valid_key_works(client, headers):
    resp = client.get("/api/tasks", headers=headers)
    assert resp.status_code == 200


# ── Key Management ──

def test_list_keys(client, headers):
    resp = client.get("/api/keys", headers=headers)
    assert resp.status_code == 200
    keys = resp.json()
    assert len(keys) >= 1
    assert keys[0]["name"] == "integration-test"


def test_create_additional_key(client, headers):
    resp = client.post("/api/keys", json={"name": "extra-key", "rate_limit": 30}, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "extra-key"
    assert data["rate_limit"] == 30
    assert data["key"].startswith("voree_")


# ── Workflows ──

def test_list_workflows(client, headers):
    resp = client.get("/api/workflows", headers=headers)
    assert resp.status_code == 200
    workflows = resp.json()
    names = [w["name"] for w in workflows]
    assert "research_v1" in names
    assert "compare_v1" in names


def test_create_custom_workflow(client, headers):
    resp = client.post("/api/workflows", json={
        "name": "test-wf",
        "instruction": "Test workflow for integration tests",
        "keywords": "integration, test",
    }, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["source"] == "custom"


def test_delete_custom_workflow(client, headers):
    resp = client.delete("/api/workflows/test-wf", headers=headers)
    assert resp.status_code == 204


def test_cannot_delete_builtin_workflow(client, headers):
    resp = client.delete("/api/workflows/research_v1", headers=headers)
    assert resp.status_code == 403


# ── Templates ──

def test_list_templates(client, headers):
    resp = client.get("/api/templates", headers=headers)
    assert resp.status_code == 200
    templates = resp.json()
    assert len(templates) >= 8
    names = [t["name"] for t in templates]
    assert "email-draft" in names


def test_list_template_categories(client, headers):
    resp = client.get("/api/templates/categories", headers=headers)
    assert resp.status_code == 200
    cats = resp.json()
    assert "writing" in cats
    assert "coding" in cats


# ── Personas ──

def test_list_personas(client, headers):
    resp = client.get("/api/personas", headers=headers)
    assert resp.status_code == 200
    personas = resp.json()
    names = [p["name"] for p in personas]
    assert "voree" in names
    assert "architect" in names
    assert len(personas) >= 6


# ── Chain Roles ──

def test_list_chain_roles(client, headers):
    resp = client.get("/api/chain/roles", headers=headers)
    assert resp.status_code == 200
    roles = resp.json()
    assert "researcher" in roles
    assert "critic" in roles
    assert "synthesizer" in roles


# ── Stats ──

def test_stats_endpoint(client, headers):
    resp = client.get("/api/stats", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "tasks" in data
    assert "memories" in data
    assert "sessions" in data
    assert "total" in data["tasks"]


# ── Memories ──

def test_memory_lifecycle(client, headers):
    # Create
    resp = client.post("/api/memories", json={"content": "Integration test memory"}, headers=headers)
    assert resp.status_code == 201
    mem_id = resp.json()["id"]

    # List
    resp = client.get("/api/memories", headers=headers)
    assert resp.status_code == 200
    assert any(m["id"] == mem_id for m in resp.json())

    # Delete
    resp = client.delete(f"/api/memories/{mem_id}", headers=headers)
    assert resp.status_code == 204


# ── Sessions ──

def test_list_sessions(client, headers):
    resp = client.get("/api/sessions", headers=headers)
    assert resp.status_code == 200


# ── Documents ──

def test_list_documents(client, headers):
    resp = client.get("/api/documents", headers=headers)
    assert resp.status_code == 200


# ── Webhooks ──

def test_webhook_lifecycle(client, headers):
    # Create
    resp = client.post("/api/webhooks", json={
        "name": "test-hook", "url": "https://httpbin.org/post", "event": "task.completed"
    }, headers=headers)
    assert resp.status_code == 201
    hook_id = resp.json()["id"]

    # List
    resp = client.get("/api/webhooks", headers=headers)
    assert resp.status_code == 200
    assert any(h["id"] == hook_id for h in resp.json())

    # Delete
    resp = client.delete(f"/api/webhooks/{hook_id}", headers=headers)
    assert resp.status_code == 204


def test_invalid_webhook_event_rejected(client, headers):
    resp = client.post("/api/webhooks", json={
        "name": "bad", "url": "https://example.com", "event": "invalid.event"
    }, headers=headers)
    assert resp.status_code == 400


# ── Schedules ──

def test_schedule_lifecycle(client, headers):
    # Create
    resp = client.post("/api/schedules", json={
        "name": "test-sched", "task": "Test scheduled task", "cron": "0 9 * * *"
    }, headers=headers)
    assert resp.status_code == 201
    sched_id = resp.json()["id"]
    assert resp.json()["next_run_at"] is not None

    # List
    resp = client.get("/api/schedules", headers=headers)
    assert resp.status_code == 200

    # Delete
    resp = client.delete(f"/api/schedules/{sched_id}", headers=headers)
    assert resp.status_code == 204


def test_invalid_cron_rejected(client, headers):
    resp = client.post("/api/schedules", json={
        "name": "bad-cron", "task": "Test", "cron": "not a cron"
    }, headers=headers)
    assert resp.status_code == 400


# ── Plugins ──

def test_plugin_lifecycle(client, headers):
    # Create
    resp = client.post("/api/plugins", json={
        "name": "test-plugin", "description": "Test plugin",
        "url": "https://httpbin.org/anything", "method": "GET",
        "parameters": {"type": "object", "properties": {}}
    }, headers=headers)
    assert resp.status_code == 201

    # List
    resp = client.get("/api/plugins", headers=headers)
    assert resp.status_code == 200
    assert any(p["name"] == "test-plugin" for p in resp.json())

    # Delete
    resp = client.delete("/api/plugins/test-plugin", headers=headers)
    assert resp.status_code == 204


# ── Security ──

def test_security_headers_on_all_responses(client):
    resp = client.get("/health")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"


def test_404_on_missing_task(client, headers):
    resp = client.get("/api/tasks/99999", headers=headers)
    assert resp.status_code == 404


def test_404_on_missing_session(client, headers):
    resp = client.get("/api/sessions/99999", headers=headers)
    assert resp.status_code == 404


# ── Export ──

def test_export_tasks_json(client, headers):
    resp = client.get("/api/export/tasks?format=json", headers=headers)
    assert resp.status_code == 200
    assert "application/json" in resp.headers["content-type"]


def test_export_tasks_csv(client, headers):
    resp = client.get("/api/export/tasks?format=csv", headers=headers)
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]


def test_export_memories_json(client, headers):
    resp = client.get("/api/export/memories?format=json", headers=headers)
    assert resp.status_code == 200
