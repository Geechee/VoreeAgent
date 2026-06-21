"""Agent core (Step 5): assemble prompt from task + workflow + memories, call Claude."""
from typing import Generator, List, Optional

import anthropic

from sqlalchemy.orm import Session as DBSession

from config import settings
from models import DocumentChunk, Memory, Message
from tools import execute_tool, get_all_tool_definitions
from workflows import get_workflow_instruction

MAX_TOOL_ROUNDS = 5

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


def _build_system_prompt(
    workflow_name: str,
    memories: Optional[List[Memory]] = None,
    db: Optional[DBSession] = None,
    doc_chunks: Optional[List[DocumentChunk]] = None,
) -> str:
    """Combine the workflow instruction with memories and document context."""
    instruction = get_workflow_instruction(workflow_name, db)
    parts = [
        "You are VOREE, an intelligent AI agent.",
        f"\n## Current Workflow\n{instruction}",
    ]
    if memories:
        memory_block = "\n".join(f"- {m.content}" for m in memories)
        parts.append(f"\n## Relevant Context from Memory\n{memory_block}")
    if doc_chunks:
        chunk_block = "\n\n---\n\n".join(
            f"[{c.document.filename} — chunk {c.chunk_index + 1}]\n{c.content}"
            for c in doc_chunks
        )
        parts.append(f"\n## Relevant Document Context\nUse the following excerpts from uploaded documents to inform your answer:\n\n{chunk_block}")
    return "\n".join(parts)


def _extract_text(message) -> str:
    return "".join(b.text for b in message.content if b.type == "text")


def _has_tool_use(message) -> bool:
    return any(b.type == "tool_use" for b in message.content)


def run_agent(
    task: str,
    workflow_name: str,
    memories: Optional[List[Memory]] = None,
    use_tools: bool = True,
    db: Optional[DBSession] = None,
    doc_chunks: Optional[List[DocumentChunk]] = None,
) -> tuple[str, list[dict]]:
    """Send the task to Claude with workflow instructions, memory context, and tools.

    Returns (response_text, tool_calls_log).
    """
    system = _build_system_prompt(workflow_name, memories, db, doc_chunks)
    messages = [{"role": "user", "content": task}]
    tools_log = []

    for _ in range(MAX_TOOL_ROUNDS):
        message = _get_client().messages.create(
            model=settings.claude_model,
            max_tokens=1024,
            system=system,
            messages=messages,
            tools=get_all_tool_definitions(db) if use_tools else [],
        )

        if not _has_tool_use(message):
            return _extract_text(message), tools_log

        messages.append({"role": "assistant", "content": message.content})

        tool_results = []
        for block in message.content:
            if block.type == "tool_use":
                result = execute_tool(block.name, block.input, db)
                tools_log.append({"tool": block.name, "input": block.input, "output": result})
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })
        messages.append({"role": "user", "content": tool_results})

    return _extract_text(message), tools_log


def stream_agent(
    task: str,
    workflow_name: str,
    memories: Optional[List[Memory]] = None,
    db: Optional[DBSession] = None,
    doc_chunks: Optional[List[DocumentChunk]] = None,
) -> Generator[str, None, None]:
    """Stream Claude's response token-by-token. Yields text deltas."""
    system = _build_system_prompt(workflow_name, memories, db, doc_chunks)
    with _get_client().messages.stream(
        model=settings.claude_model,
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": task}],
    ) as stream:
        for text in stream.text_stream:
            yield text


def run_conversation(
    messages: List[Message],
    workflow_name: str,
    memories: Optional[List[Memory]] = None,
    db: Optional[DBSession] = None,
    doc_chunks: Optional[List[DocumentChunk]] = None,
) -> str:
    """Send a full conversation history to Claude and return the next response."""
    system = _build_system_prompt(workflow_name, memories, db, doc_chunks)
    history = [{"role": m.role, "content": m.content} for m in messages]
    message = _get_client().messages.create(
        model=settings.claude_model,
        max_tokens=1024,
        system=system,
        messages=history,
    )
    return message.content[0].text
