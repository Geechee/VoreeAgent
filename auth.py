"""API key authentication and rate limiting for VOREE endpoints."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session
from sqlalchemy import func

from db import get_db
from models import ApiKey, UsageLog

_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def generate_key() -> str:
    return "voree_" + secrets.token_urlsafe(32)


def create_api_key(db: Session, name: str, rate_limit: int = 60) -> tuple[str, ApiKey]:
    """Generate a new API key. Returns (raw_key, db_row). The raw key is only shown once."""
    raw = generate_key()
    row = ApiKey(name=name, key_hash=hash_key(raw), rate_limit=rate_limit)
    db.add(row)
    db.commit()
    db.refresh(row)
    return raw, row


def _check_rate_limit(db: Session, api_key: ApiKey):
    """Enforce per-key requests-per-minute limit."""
    one_minute_ago = datetime.now(timezone.utc) - timedelta(minutes=1)
    recent_count = (
        db.query(func.count(UsageLog.id))
        .filter(
            UsageLog.api_key_id == api_key.id,
            UsageLog.created_at >= one_minute_ago,
        )
        .scalar()
    )
    if recent_count >= api_key.rate_limit:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: {api_key.rate_limit} requests/minute. Try again shortly.",
            headers={"Retry-After": "60"},
        )


def log_usage(db: Session, api_key: ApiKey, endpoint: str, method: str, status_code: int = 200):
    """Record an API call for usage tracking."""
    log = UsageLog(
        api_key_id=api_key.id,
        endpoint=endpoint,
        method=method,
        status_code=status_code,
    )
    db.add(log)
    db.commit()


def require_key(
    request: Request,
    key: str = Security(_header),
    db: Session = Depends(get_db),
) -> ApiKey:
    if key is None:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")
    row = db.query(ApiKey).filter(ApiKey.key_hash == hash_key(key), ApiKey.is_active == True).first()
    if not row:
        raise HTTPException(status_code=403, detail="Invalid or revoked API key")
    _check_rate_limit(db, row)
    log_usage(db, row, request.url.path, request.method)
    return row
