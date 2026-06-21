"""Tests for database models — verify schema definitions."""
from models import (
    Task, Memory, Session, Message, Critique, CustomWorkflow,
    Document, DocumentChunk, ApiKey, UsageLog, Webhook, Schedule,
    Plugin, Template, Persona,
)


def test_all_models_have_tablenames():
    models = [
        Task, Memory, Session, Message, Critique, CustomWorkflow,
        Document, DocumentChunk, ApiKey, UsageLog, Webhook, Schedule,
        Plugin, Template, Persona,
    ]
    tablenames = [m.__tablename__ for m in models]
    assert len(tablenames) == 15
    assert len(set(tablenames)) == 15, "Duplicate table names"


def test_task_columns():
    cols = {c.name for c in Task.__table__.columns}
    assert {"id", "input", "workflow", "status", "result", "score", "created_at"}.issubset(cols)


def test_memory_has_embedding():
    cols = {c.name for c in Memory.__table__.columns}
    assert "embedding" in cols


def test_session_has_messages_relationship():
    assert hasattr(Session, "messages")


def test_apikey_has_rate_limit():
    cols = {c.name for c in ApiKey.__table__.columns}
    assert "rate_limit" in cols


def test_document_has_chunks_relationship():
    assert hasattr(Document, "chunks")


def test_webhook_columns():
    cols = {c.name for c in Webhook.__table__.columns}
    assert {"name", "url", "event", "secret", "is_active"}.issubset(cols)


def test_schedule_columns():
    cols = {c.name for c in Schedule.__table__.columns}
    assert {"name", "task", "cron", "is_active", "next_run_at"}.issubset(cols)


def test_plugin_columns():
    cols = {c.name for c in Plugin.__table__.columns}
    assert {"name", "description", "url", "method", "parameters_json"}.issubset(cols)
