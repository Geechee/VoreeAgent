"""Multi-agent collaboration — chain agents with distinct roles into a pipeline."""
from typing import List, Optional

import anthropic

from config import settings
from models import Memory, DocumentChunk
from workflows import get_workflow_instruction

_client = None

AGENT_ROLES = {
    "researcher": (
        "You are a thorough researcher. Investigate the topic deeply and produce "
        "comprehensive, well-organized findings with concrete details. Focus on "
        "accuracy and completeness."
    ),
    "critic": (
        "You are a rigorous critic. Review the provided analysis for errors, gaps, "
        "weak reasoning, and missing perspectives. Be specific about what's wrong "
        "and what's missing. Don't be nice — be thorough."
    ),
    "synthesizer": (
        "You are an expert synthesizer. Take the original research and the critic's "
        "feedback and produce a final, polished answer that addresses all identified "
        "gaps and corrections. The result should be better than either input alone."
    ),
    "creative": (
        "You are a creative thinker. Approach the topic from unexpected angles. "
        "Generate novel insights, analogies, and ideas that a conventional analysis "
        "would miss."
    ),
    "simplifier": (
        "You are an expert simplifier. Take complex material and rewrite it so a "
        "complete beginner can understand it. Use simple language, real-world "
        "analogies, and short sentences. No jargon unless defined."
    ),
}


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


def _run_agent_role(
    role: str,
    task: str,
    prior_outputs: List[dict],
    memories: Optional[List[Memory]] = None,
    doc_chunks: Optional[List[DocumentChunk]] = None,
) -> str:
    role_instruction = AGENT_ROLES.get(role, AGENT_ROLES["researcher"])

    parts = [f"You are VOREE Agent ({role} role).", f"\n## Your Role\n{role_instruction}"]

    if memories:
        mem_block = "\n".join(f"- {m.content}" for m in memories)
        parts.append(f"\n## Relevant Memory\n{mem_block}")

    if doc_chunks:
        chunk_block = "\n\n---\n\n".join(
            f"[{c.document.filename} — chunk {c.chunk_index + 1}]\n{c.content}"
            for c in doc_chunks
        )
        parts.append(f"\n## Document Context\n{chunk_block}")

    if prior_outputs:
        for p in prior_outputs:
            parts.append(f"\n## Output from {p['role']} agent\n{p['output']}")

    system = "\n".join(parts)

    message = _get_client().messages.create(
        model=settings.claude_model,
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": task}],
    )
    return message.content[0].text


def run_chain(
    task: str,
    roles: List[str],
    memories: Optional[List[Memory]] = None,
    doc_chunks: Optional[List[DocumentChunk]] = None,
) -> dict:
    """Run a chain of agents sequentially. Each agent sees all prior outputs.

    Returns {steps: [{role, output}], final_result: str}.
    """
    steps = []
    for role in roles:
        output = _run_agent_role(task, role, steps, memories, doc_chunks)
        steps.append({"role": role, "output": output})

    return {
        "steps": steps,
        "final_result": steps[-1]["output"] if steps else "",
    }
