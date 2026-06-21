"""Webhook delivery system — fires HTTP POSTs when events occur."""
import hashlib
import hmac
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from models import Webhook

logger = logging.getLogger("voree.webhooks")
_executor = ThreadPoolExecutor(max_workers=3)


def _sign_payload(payload: str, secret: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def _deliver(webhook: Webhook, payload: dict):
    """Send the webhook HTTP POST. Retries once on failure."""
    body = json.dumps(payload)
    headers = {"Content-Type": "application/json", "X-Voree-Event": webhook.event}
    if webhook.secret:
        headers["X-Voree-Signature"] = _sign_payload(body, webhook.secret)

    for attempt in range(2):
        try:
            resp = httpx.post(webhook.url, content=body, headers=headers, timeout=10)
            logger.info(f"Webhook {webhook.name} -> {resp.status_code}")
            return
        except Exception as e:
            logger.warning(f"Webhook {webhook.name} attempt {attempt+1} failed: {e}")


def fire_event(db: Session, event: str, payload: dict):
    """Find all active webhooks for the given event and deliver asynchronously."""
    hooks = db.query(Webhook).filter(
        Webhook.event == event, Webhook.is_active == True
    ).all()
    for hook in hooks:
        _executor.submit(_deliver, hook, payload)


def fire_task_completed(db: Session, task_id: int, task_input: str, workflow: str,
                        result: str, score: Optional[int]):
    payload = {
        "event": "task.completed",
        "task": {
            "id": task_id,
            "input": task_input,
            "workflow": workflow,
            "result": result[:500],
            "score": score,
        },
    }
    fire_event(db, "task.completed", payload)
