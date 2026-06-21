"""Critic system (Step 7): score Claude's output and retry once if weak."""
import json
import re

import anthropic

from config import settings

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


def critique(task: str, result: str) -> dict:
    """Ask Claude to score the result 1-10 and explain why."""
    message = _get_client().messages.create(
        model=settings.claude_model,
        max_tokens=256,
        system=(
            "You are a strict quality reviewer. Score the given AI response on a "
            "scale of 1-10 based on accuracy, completeness, and usefulness. "
            "Respond with ONLY valid JSON: {\"score\": <int>, \"feedback\": \"<reason>\"}"
        ),
        messages=[
            {
                "role": "user",
                "content": f"Task: {task}\n\nResponse to evaluate:\n{result}",
            }
        ],
    )
    text = message.content[0].text.strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group())
    return {"score": 5, "feedback": "Could not parse critic response."}
