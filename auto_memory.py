"""Auto-memory system — extracts key facts from conversations for long-term learning."""
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import anthropic

from config import settings
from db import SessionLocal
from memory import store_memory

logger = logging.getLogger("voree.auto_memory")
_client = None
_executor = ThreadPoolExecutor(max_workers=2)


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


def _extract_facts(task: str, result: str) -> list[str]:
    """Ask Claude to extract memorable facts from a task interaction."""
    message = _get_client().messages.create(
        model=settings.claude_model,
        max_tokens=512,
        system=(
            "You extract key facts from task interactions that would be useful to remember for future tasks. "
            "Extract facts about: the user's tech stack, preferences, constraints, team details, "
            "decisions made, tools chosen, problems encountered, and lessons learned. "
            "Each fact should be a standalone sentence. Extract 1-3 facts. "
            "Respond with ONLY a JSON array of strings. Example: [\"Team uses PostgreSQL on Railway\", \"Budget is limited\"]"
        ),
        messages=[{
            "role": "user",
            "content": f"Extract memorable facts from this interaction:\n\nUser asked: {task}\n\nResponse given: {result[:800]}",
        }],
    )
    try:
        text = message.content[0].text.strip()
        logger.info(f"Raw extraction response: {text[:200]}")
        # Find JSON array in the response
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            facts = json.loads(text[start:end])
            return [f for f in facts if isinstance(f, str) and len(f) > 10]
    except (json.JSONDecodeError, IndexError) as e:
        logger.error(f"Failed to parse facts: {e}")
    return []


def _process_extraction(task: str, result: str):
    """Extract facts and store them as memories."""
    db = SessionLocal()
    try:
        logger.info(f"Extracting facts from: {task[:60]}...")
        facts = _extract_facts(task, result)
        logger.info(f"Extracted {len(facts)} facts")
        for fact in facts[:3]:
            logger.info(f"Storing: {fact[:60]}...")
            store_memory(db, f"[auto] {fact}")
            logger.info(f"Auto-memory stored: {fact[:60]}")
    except Exception as e:
        logger.error(f"Auto-memory extraction failed: {e}", exc_info=True)
    finally:
        db.close()


def extract_and_store(task: str, result: str):
    """Fire-and-forget: extract facts from a task result in the background."""
    _executor.submit(_process_extraction, task, result)


def extract_from_session(messages: list[dict]) -> list[str]:
    """Extract facts from a multi-turn conversation."""
    conversation = "\n".join(
        f"{m['role'].upper()}: {m['content'][:300]}" for m in messages[-10:]
    )
    message = _get_client().messages.create(
        model=settings.claude_model,
        max_tokens=512,
        system=(
            "You extract key facts worth remembering from conversations. "
            "Focus on: user preferences, decisions, technical choices, "
            "constraints, project context, and lessons learned. "
            "Return a JSON array of short fact strings. "
            "Only include facts useful in future conversations. "
            "If nothing is worth remembering, return []. "
            "Return ONLY the JSON array."
        ),
        messages=[{"role": "user", "content": conversation}],
    )
    try:
        text = message.content[0].text.strip()
        if text.startswith("["):
            return [f for f in json.loads(text) if isinstance(f, str) and len(f) > 10]
    except (json.JSONDecodeError, IndexError):
        pass
    return []
