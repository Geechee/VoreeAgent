"""VOREE MCP Server — expose VOREE capabilities as MCP tools for Claude Desktop and other AI tools."""
import json
import os

from mcp.server.fastmcp import FastMCP

# VOREE internals
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://voree:voree@db:5432/voree")

from agent import run_agent
from chain import run_chain, AGENT_ROLES
from db import SessionLocal, init_db
from memory import retrieve_memories, store_memory
from rag import retrieve_chunks
from templates import BUILTIN_TEMPLATES, render_template
from workflows import select_workflow

mcp = FastMCP(
    "VOREE Agent",
    description="AI agent backend with semantic memory, RAG, multi-agent chains, and templates",
)


def _get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@mcp.tool()
def voree_task(task: str, persona: str = "") -> str:
    """Run a task through the VOREE agent pipeline. Includes workflow routing, semantic memory, document RAG, tool use, and quality critique.

    Args:
        task: The task to process (e.g. "Research the top 3 Python web frameworks")
        persona: Optional persona name (architect, mentor, strategist, devil, creative)
    """
    db = SessionLocal()
    try:
        workflow = select_workflow(task, db)
        memories = retrieve_memories(db, task, k=5)
        doc_chunks = retrieve_chunks(db, task, k=5)
        from personas import get_persona_prompt
        persona_prompt = get_persona_prompt(persona, db) if persona else None
        result, tools_log = run_agent(
            task, workflow, memories, db=db,
            doc_chunks=doc_chunks or None,
            persona_prompt=persona_prompt,
        )
        store_memory(db, f"Task: {task} | Result summary: {result[:200]}")
        return result
    finally:
        db.close()


@mcp.tool()
def voree_chain(task: str, roles: str = "researcher,critic,synthesizer") -> str:
    """Run a multi-agent chain where each agent builds on the previous one's output.

    Args:
        task: The task for the chain to process
        roles: Comma-separated agent roles (researcher, critic, synthesizer, creative, simplifier)
    """
    db = SessionLocal()
    try:
        role_list = [r.strip() for r in roles.split(",")]
        memories = retrieve_memories(db, task, k=5)
        doc_chunks = retrieve_chunks(db, task, k=5)
        result = run_chain(task, role_list, memories, doc_chunks or None)
        return result["final_result"]
    finally:
        db.close()


@mcp.tool()
def voree_remember(content: str) -> str:
    """Store a memory in VOREE's semantic memory bank for future context.

    Args:
        content: The information to remember
    """
    db = SessionLocal()
    try:
        mem = store_memory(db, content)
        return f"Stored memory #{mem.id}: {content[:100]}"
    finally:
        db.close()


@mcp.tool()
def voree_recall(query: str, k: int = 5) -> str:
    """Search VOREE's semantic memory for relevant past context.

    Args:
        query: What to search for (uses meaning-based similarity, not keyword matching)
        k: Number of results to return (default 5)
    """
    db = SessionLocal()
    try:
        memories = retrieve_memories(db, query, k=k)
        if not memories:
            return "No relevant memories found."
        return "\n\n".join(f"[Memory #{m.id}] {m.content}" for m in memories)
    finally:
        db.close()


@mcp.tool()
def voree_search_docs(query: str, k: int = 5) -> str:
    """Search uploaded documents for relevant content using semantic similarity.

    Args:
        query: What to search for in the documents
        k: Number of chunks to return (default 5)
    """
    db = SessionLocal()
    try:
        chunks = retrieve_chunks(db, query, k=k)
        if not chunks:
            return "No relevant document chunks found."
        return "\n\n---\n\n".join(
            f"[{c.document.filename} — chunk {c.chunk_index + 1}]\n{c.content}"
            for c in chunks
        )
    finally:
        db.close()


@mcp.tool()
def voree_template(name: str, variables: str = "{}") -> str:
    """Run a pre-built template with variable substitution.

    Args:
        name: Template name (email-draft, code-review, meeting-summary, blog-post, pros-cons, explain-concept, user-story, brainstorm-ideas)
        variables: JSON string of variable values (e.g. '{"topic": "AI agents", "recipient": "my team"}')
    """
    db = SessionLocal()
    try:
        tmpl = None
        for t in BUILTIN_TEMPLATES:
            if t["name"] == name:
                tmpl = t
                break
        if not tmpl:
            return f"Template '{name}' not found. Available: {', '.join(t['name'] for t in BUILTIN_TEMPLATES)}"

        vars_dict = json.loads(variables)
        filled = dict(vars_dict)
        for v in tmpl["variables"]:
            if v["name"] not in filled and "default" in v:
                filled[v["name"]] = v["default"]

        task_text = render_template(tmpl["prompt"], filled)
        workflow = select_workflow(task_text, db)
        memories = retrieve_memories(db, task_text, k=5)
        result, _ = run_agent(task_text, workflow, memories, db=db)
        return result
    finally:
        db.close()


@mcp.tool()
def voree_list_templates() -> str:
    """List all available VOREE templates with their descriptions and required variables."""
    lines = []
    for t in BUILTIN_TEMPLATES:
        vars_desc = ", ".join(
            f"{v['name']}{'*' if v.get('required') else ''}"
            for v in t["variables"]
        )
        lines.append(f"- {t['name']} [{t['category']}]: {t['description']} (vars: {vars_desc})")
    return "\n".join(lines)


@mcp.tool()
def voree_list_roles() -> str:
    """List available agent roles for multi-agent chains."""
    return "\n".join(f"- {name}: {desc[:80]}" for name, desc in AGENT_ROLES.items())


if __name__ == "__main__":
    init_db()
    mcp.run(transport="stdio")
