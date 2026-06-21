"""Tests for configuration and database URL handling."""
import os


def test_database_url_conversion():
    os.environ["DATABASE_URL"] = "postgresql://user:pass@host:5432/db"
    os.environ.pop("ANTHROPIC_API_KEY", None)
    os.environ.pop("VOYAGE_API_KEY", None)

    from importlib import reload
    import config
    reload(config)

    assert config.settings.database_url.startswith("postgresql+psycopg2://")


def test_database_url_no_conversion_needed():
    os.environ["DATABASE_URL"] = "postgresql+psycopg2://user:pass@host:5432/db"
    os.environ.pop("ANTHROPIC_API_KEY", None)
    os.environ.pop("VOYAGE_API_KEY", None)

    from importlib import reload
    import config
    reload(config)

    assert config.settings.database_url == "postgresql+psycopg2://user:pass@host:5432/db"


def test_default_model():
    from config import settings
    assert "claude" in settings.claude_model


def test_default_embedding_dim():
    from config import settings
    assert settings.embedding_dim == 1024
