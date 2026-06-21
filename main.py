"""VOREE Agent Framework v1.1 — FastAPI entrypoint."""
from contextlib import asynccontextmanager
from typing import List, Optional
import csv
import io
import json

from fastapi import FastAPI, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

import models  # noqa: F401  registers tables on Base
from agent import run_agent, run_conversation, stream_agent
from auth import create_api_key, require_key
from chain import run_chain, AGENT_ROLES
from critic import critique
from db import check_connection, get_db, init_db
from memory import retrieve_memories, store_memory
from rag import ingest_document, retrieve_chunks
from scheduler import start_scheduler, stop_scheduler
from webhooks import fire_task_completed
from worker import submit_task
from workflows import BUILTIN_WORKFLOWS, select_workflow


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="VOREE Agent Framework", version="1.1", lifespan=lifespan)


class TaskRequest(BaseModel):
    task: str


class ToolCall(BaseModel):
    tool: str
    input: dict
    output: str


class TaskResponse(BaseModel):
    task: str
    workflow: str
    result: str
    memories_used: int
    score: int
    retried: bool
    tools_used: List[ToolCall]


@app.post("/api/task")
def handle_task(req: TaskRequest, db: Session = Depends(get_db), _key=Depends(require_key)):
    workflow = select_workflow(req.task, db)
    memories = retrieve_memories(db, req.task, k=5)
    doc_chunks = retrieve_chunks(db, req.task, k=5)
    result, tools_log = run_agent(req.task, workflow, memories, db=db, doc_chunks=doc_chunks or None)

    # Critic scores the result
    review = critique(req.task, result)
    score = review["score"]
    retried = False

    # Retry once if score is below 7
    if score < 7:
        result, tools_log = run_agent(req.task, workflow, memories, db=db, doc_chunks=doc_chunks or None)
        review = critique(req.task, result)
        score = review["score"]
        retried = True

    # Save the task to the database
    task_row = models.Task(input=req.task, workflow=workflow, result=result, score=score)
    db.add(task_row)
    db.commit()
    db.refresh(task_row)

    # Save the critique
    critique_row = models.Critique(
        task_id=task_row.id, score=score, feedback=review["feedback"]
    )
    db.add(critique_row)
    db.commit()

    # Store the result as a new memory for future context
    store_memory(db, f"Task: {req.task} | Result summary: {result[:200]}")

    # Fire webhooks
    fire_task_completed(db, task_row.id, req.task, workflow, result, score)

    return TaskResponse(
        task=req.task,
        workflow=workflow,
        result=result,
        memories_used=len(memories),
        score=score,
        retried=retried,
        tools_used=[ToolCall(**t) for t in tools_log],
    )


@app.post("/api/task/stream")
def handle_task_stream(req: TaskRequest, db: Session = Depends(get_db), _key=Depends(require_key)):
    workflow = select_workflow(req.task, db)
    memories = retrieve_memories(db, req.task, k=5)

    def event_stream():
        meta = json.dumps({"workflow": workflow, "memories_used": len(memories)})
        yield f"event: meta\ndata: {meta}\n\n"

        full_result = []
        for token in stream_agent(req.task, workflow, memories, db=db):
            full_result.append(token)
            yield f"data: {json.dumps(token)}\n\n"

        # Save task and memory after streaming completes
        result_text = "".join(full_result)
        task_row = models.Task(input=req.task, workflow=workflow, result=result_text)
        db.add(task_row)
        db.commit()
        store_memory(db, f"Task: {req.task} | Result summary: {result_text[:200]}")

        yield f"event: done\ndata: {json.dumps({'status': 'complete'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


class AsyncTaskResponse(BaseModel):
    task_id: int
    status: str
    message: str


class TaskStatus(BaseModel):
    id: int
    task: str
    status: str
    workflow: Optional[str]
    result: Optional[str]
    error: Optional[str]
    score: Optional[int]
    created_at: str
    completed_at: Optional[str]


@app.post("/api/task/async", response_model=AsyncTaskResponse, status_code=202)
def handle_task_async(req: TaskRequest, db: Session = Depends(get_db), _key=Depends(require_key)):
    task_row = models.Task(input=req.task, status="pending")
    db.add(task_row)
    db.commit()
    db.refresh(task_row)
    submit_task(task_row.id)
    return AsyncTaskResponse(
        task_id=task_row.id,
        status="pending",
        message="Task submitted. Poll GET /api/task/async/{task_id} for results.",
    )


@app.get("/api/task/async/{task_id}", response_model=TaskStatus)
def get_task_status(task_id: int, db: Session = Depends(get_db), _key=Depends(require_key)):
    task_row = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task_row:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskStatus(
        id=task_row.id,
        task=task_row.input,
        status=task_row.status or "completed",
        workflow=task_row.workflow,
        result=task_row.result,
        error=task_row.error,
        score=task_row.score,
        created_at=task_row.created_at.isoformat(),
        completed_at=task_row.completed_at.isoformat() if task_row.completed_at else None,
    )


# ── Multi-agent chains ──


class ChainRequest(BaseModel):
    task: str
    roles: List[str] = ["researcher", "critic", "synthesizer"]


class ChainStep(BaseModel):
    role: str
    output: str


class ChainResponse(BaseModel):
    task: str
    roles: List[str]
    steps: List[ChainStep]
    final_result: str


@app.get("/api/chain/roles")
def list_roles(_key=Depends(require_key)):
    return {name: desc for name, desc in AGENT_ROLES.items()}


@app.post("/api/chain", response_model=ChainResponse)
def run_agent_chain(req: ChainRequest, db: Session = Depends(get_db), _key=Depends(require_key)):
    for role in req.roles:
        if role not in AGENT_ROLES:
            raise HTTPException(status_code=400, detail=f"Unknown role: {role}. Valid: {list(AGENT_ROLES.keys())}")
    if len(req.roles) < 2:
        raise HTTPException(status_code=400, detail="Chain requires at least 2 roles")

    memories = retrieve_memories(db, req.task, k=5)
    doc_chunks = retrieve_chunks(db, req.task, k=5)
    result = run_chain(req.task, req.roles, memories, doc_chunks or None)

    task_row = models.Task(
        input=f"[chain:{','.join(req.roles)}] {req.task}",
        workflow="chain",
        result=result["final_result"],
        status="completed",
    )
    db.add(task_row)
    db.commit()

    store_memory(db, f"Task: {req.task} | Chain result: {result['final_result'][:200]}")

    return ChainResponse(
        task=req.task,
        roles=req.roles,
        steps=[ChainStep(**s) for s in result["steps"]],
        final_result=result["final_result"],
    )


class TaskSummary(BaseModel):
    id: int
    task: str
    workflow: Optional[str]
    status: str
    score: Optional[int]
    created_at: str


class TaskDetail(BaseModel):
    id: int
    task: str
    workflow: str
    result: str
    score: Optional[int]
    critique_feedback: Optional[str]
    created_at: str


@app.get("/api/tasks", response_model=List[TaskSummary])
def list_tasks(
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    workflow: Optional[str] = Query(default=None),
    min_score: Optional[int] = Query(default=None, ge=1, le=10),
    db: Session = Depends(get_db),
    _key=Depends(require_key),
):
    query = db.query(models.Task).order_by(desc(models.Task.created_at))
    if workflow:
        query = query.filter(models.Task.workflow == workflow)
    if min_score is not None:
        query = query.filter(models.Task.score >= min_score)
    rows = query.offset(offset).limit(limit).all()
    return [
        TaskSummary(
            id=r.id,
            task=r.input,
            workflow=r.workflow,
            status=r.status or "completed",
            score=r.score,
            created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]


@app.get("/api/tasks/{task_id}", response_model=TaskDetail)
def get_task(task_id: int, db: Session = Depends(get_db), _key=Depends(require_key)):
    task_row = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task_row:
        raise HTTPException(status_code=404, detail="Task not found")
    critique_row = (
        db.query(models.Critique)
        .filter(models.Critique.task_id == task_id)
        .order_by(desc(models.Critique.created_at))
        .first()
    )
    return TaskDetail(
        id=task_row.id,
        task=task_row.input,
        workflow=task_row.workflow,
        result=task_row.result or "",
        score=task_row.score,
        critique_feedback=critique_row.feedback if critique_row else None,
        created_at=task_row.created_at.isoformat(),
    )


# ── Memory management ──


class MemoryOut(BaseModel):
    id: int
    content: str
    created_at: str


class MemoryCreate(BaseModel):
    content: str


class MemorySearchRequest(BaseModel):
    query: str
    k: int = 5


@app.get("/api/memories", response_model=List[MemoryOut])
def list_memories(
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _key=Depends(require_key),
):
    rows = (
        db.query(models.Memory)
        .order_by(desc(models.Memory.created_at))
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        MemoryOut(id=r.id, content=r.content, created_at=r.created_at.isoformat())
        for r in rows
    ]


@app.post("/api/memories", response_model=MemoryOut, status_code=201)
def create_memory(req: MemoryCreate, db: Session = Depends(get_db), _key=Depends(require_key)):
    mem = store_memory(db, req.content)
    return MemoryOut(id=mem.id, content=mem.content, created_at=mem.created_at.isoformat())


@app.post("/api/memories/search", response_model=List[MemoryOut])
def search_memories(req: MemorySearchRequest, db: Session = Depends(get_db), _key=Depends(require_key)):
    results = retrieve_memories(db, req.query, k=req.k)
    return [
        MemoryOut(id=r.id, content=r.content, created_at=r.created_at.isoformat())
        for r in results
    ]


@app.delete("/api/memories/{memory_id}", status_code=204)
def delete_memory(memory_id: int, db: Session = Depends(get_db), _key=Depends(require_key)):
    mem = db.query(models.Memory).filter(models.Memory.id == memory_id).first()
    if not mem:
        raise HTTPException(status_code=404, detail="Memory not found")
    db.delete(mem)
    db.commit()


# ── Multi-turn conversations ──


class SessionOut(BaseModel):
    id: int
    title: Optional[str]
    workflow: str
    message_count: int
    created_at: str


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: str


class SessionDetail(BaseModel):
    id: int
    title: Optional[str]
    workflow: str
    messages: List[MessageOut]
    created_at: str


class SessionCreate(BaseModel):
    message: str
    workflow: Optional[str] = None


class SessionReply(BaseModel):
    message: str


@app.post("/api/sessions", response_model=SessionDetail, status_code=201)
def create_session(req: SessionCreate, db: Session = Depends(get_db), _key=Depends(require_key)):
    workflow = req.workflow or select_workflow(req.message, db)
    memories = retrieve_memories(db, req.message, k=5)

    session = models.Session(title=req.message[:80], workflow=workflow)
    db.add(session)
    db.commit()
    db.refresh(session)

    user_msg = models.Message(session_id=session.id, role="user", content=req.message)
    db.add(user_msg)
    db.commit()
    db.refresh(user_msg)

    reply = run_conversation([user_msg], workflow, memories, db=db)

    asst_msg = models.Message(session_id=session.id, role="assistant", content=reply)
    db.add(asst_msg)
    db.commit()
    db.refresh(asst_msg)

    return SessionDetail(
        id=session.id,
        title=session.title,
        workflow=workflow,
        messages=[
            MessageOut(id=user_msg.id, role="user", content=user_msg.content, created_at=user_msg.created_at.isoformat()),
            MessageOut(id=asst_msg.id, role="assistant", content=asst_msg.content, created_at=asst_msg.created_at.isoformat()),
        ],
        created_at=session.created_at.isoformat(),
    )


@app.post("/api/sessions/{session_id}/reply", response_model=MessageOut)
def reply_to_session(session_id: int, req: SessionReply, db: Session = Depends(get_db), _key=Depends(require_key)):
    session = db.query(models.Session).filter(models.Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    user_msg = models.Message(session_id=session.id, role="user", content=req.message)
    db.add(user_msg)
    db.commit()

    all_messages = (
        db.query(models.Message)
        .filter(models.Message.session_id == session.id)
        .order_by(models.Message.created_at)
        .all()
    )

    memories = retrieve_memories(db, req.message, k=5)
    reply = run_conversation(all_messages, session.workflow, memories, db=db)

    asst_msg = models.Message(session_id=session.id, role="assistant", content=reply)
    db.add(asst_msg)
    db.commit()
    db.refresh(asst_msg)

    return MessageOut(id=asst_msg.id, role="assistant", content=asst_msg.content, created_at=asst_msg.created_at.isoformat())


@app.get("/api/sessions", response_model=List[SessionOut])
def list_sessions(
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _key=Depends(require_key),
):
    rows = (
        db.query(models.Session)
        .order_by(desc(models.Session.created_at))
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        SessionOut(
            id=r.id,
            title=r.title,
            workflow=r.workflow,
            message_count=len(r.messages),
            created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]


@app.get("/api/sessions/{session_id}", response_model=SessionDetail)
def get_session(session_id: int, db: Session = Depends(get_db), _key=Depends(require_key)):
    session = db.query(models.Session).filter(models.Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionDetail(
        id=session.id,
        title=session.title,
        workflow=session.workflow,
        messages=[
            MessageOut(id=m.id, role=m.role, content=m.content, created_at=m.created_at.isoformat())
            for m in session.messages
        ],
        created_at=session.created_at.isoformat(),
    )


# ── Documents & RAG ──

ALLOWED_TYPES = {"text/plain", "text/markdown", "application/pdf"}


class DocumentOut(BaseModel):
    id: int
    filename: str
    content_type: str
    size_bytes: int
    chunk_count: int
    created_at: str


class ChunkOut(BaseModel):
    id: int
    document_id: int
    filename: str
    chunk_index: int
    content: str


@app.post("/api/documents", response_model=DocumentOut, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _key=Depends(require_key),
):
    if file.content_type not in ALLOWED_TYPES and not file.filename.endswith((".txt", ".md")):
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.content_type}. Use .txt or .md files.")
    raw = await file.read()
    text = raw.decode("utf-8", errors="replace")
    if not text.strip():
        raise HTTPException(status_code=400, detail="File is empty")
    doc = ingest_document(db, file.filename, file.content_type or "text/plain", text)
    return DocumentOut(
        id=doc.id, filename=doc.filename, content_type=doc.content_type,
        size_bytes=doc.size_bytes, chunk_count=doc.chunk_count,
        created_at=doc.created_at.isoformat(),
    )


@app.get("/api/documents", response_model=List[DocumentOut])
def list_documents(db: Session = Depends(get_db), _key=Depends(require_key)):
    rows = db.query(models.Document).order_by(desc(models.Document.created_at)).all()
    return [
        DocumentOut(
            id=r.id, filename=r.filename, content_type=r.content_type,
            size_bytes=r.size_bytes, chunk_count=r.chunk_count,
            created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]


@app.delete("/api/documents/{doc_id}", status_code=204)
def delete_document(doc_id: int, db: Session = Depends(get_db), _key=Depends(require_key)):
    doc = db.query(models.Document).filter(models.Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    db.query(models.DocumentChunk).filter(models.DocumentChunk.document_id == doc_id).delete()
    db.delete(doc)
    db.commit()


class DocSearchRequest(BaseModel):
    query: str
    k: int = 5


@app.post("/api/documents/search", response_model=List[ChunkOut])
def search_documents(req: DocSearchRequest, db: Session = Depends(get_db), _key=Depends(require_key)):
    chunks = retrieve_chunks(db, req.query, k=req.k)
    return [
        ChunkOut(
            id=c.id, document_id=c.document_id, filename=c.document.filename,
            chunk_index=c.chunk_index, content=c.content,
        )
        for c in chunks
    ]


# ── Custom workflows ──


class WorkflowCreate(BaseModel):
    name: str
    instruction: str
    keywords: str  # comma-separated


class WorkflowUpdate(BaseModel):
    instruction: Optional[str] = None
    keywords: Optional[str] = None
    is_active: Optional[bool] = None


class WorkflowOut(BaseModel):
    id: Optional[int] = None
    name: str
    instruction: str
    keywords: str
    is_active: bool
    source: str  # "builtin" or "custom"
    created_at: Optional[str] = None


@app.get("/api/workflows", response_model=List[WorkflowOut])
def list_workflows(db: Session = Depends(get_db), _key=Depends(require_key)):
    results = []
    from workflows import _BUILTIN_KEYWORDS
    for name, instruction in BUILTIN_WORKFLOWS.items():
        kw = next((kws for n, kws in _BUILTIN_KEYWORDS if n == name), [])
        results.append(WorkflowOut(
            name=name, instruction=instruction, keywords=", ".join(kw),
            is_active=True, source="builtin",
        ))
    customs = db.query(models.CustomWorkflow).order_by(models.CustomWorkflow.created_at).all()
    for c in customs:
        results.append(WorkflowOut(
            id=c.id, name=c.name, instruction=c.instruction, keywords=c.keywords,
            is_active=c.is_active, source="custom", created_at=c.created_at.isoformat(),
        ))
    return results


@app.post("/api/workflows", response_model=WorkflowOut, status_code=201)
def create_workflow(req: WorkflowCreate, db: Session = Depends(get_db), _key=Depends(require_key)):
    if req.name in BUILTIN_WORKFLOWS:
        raise HTTPException(status_code=409, detail=f"'{req.name}' is a built-in workflow and cannot be overridden")
    existing = db.query(models.CustomWorkflow).filter(models.CustomWorkflow.name == req.name).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Workflow '{req.name}' already exists")
    row = models.CustomWorkflow(name=req.name, instruction=req.instruction, keywords=req.keywords)
    db.add(row)
    db.commit()
    db.refresh(row)
    return WorkflowOut(
        id=row.id, name=row.name, instruction=row.instruction, keywords=row.keywords,
        is_active=row.is_active, source="custom", created_at=row.created_at.isoformat(),
    )


@app.put("/api/workflows/{name}", response_model=WorkflowOut)
def update_workflow(name: str, req: WorkflowUpdate, db: Session = Depends(get_db), _key=Depends(require_key)):
    if name in BUILTIN_WORKFLOWS:
        raise HTTPException(status_code=403, detail="Cannot modify built-in workflows")
    row = db.query(models.CustomWorkflow).filter(models.CustomWorkflow.name == name).first()
    if not row:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if req.instruction is not None:
        row.instruction = req.instruction
    if req.keywords is not None:
        row.keywords = req.keywords
    if req.is_active is not None:
        row.is_active = req.is_active
    db.commit()
    db.refresh(row)
    return WorkflowOut(
        id=row.id, name=row.name, instruction=row.instruction, keywords=row.keywords,
        is_active=row.is_active, source="custom", created_at=row.created_at.isoformat(),
    )


@app.delete("/api/workflows/{name}", status_code=204)
def delete_workflow(name: str, db: Session = Depends(get_db), _key=Depends(require_key)):
    if name in BUILTIN_WORKFLOWS:
        raise HTTPException(status_code=403, detail="Cannot delete built-in workflows")
    row = db.query(models.CustomWorkflow).filter(models.CustomWorkflow.name == name).first()
    if not row:
        raise HTTPException(status_code=404, detail="Workflow not found")
    db.delete(row)
    db.commit()


# ── API key management ──


class KeyCreate(BaseModel):
    name: str
    rate_limit: int = 60


class KeyOut(BaseModel):
    id: int
    name: str
    key: Optional[str] = None
    is_active: bool
    rate_limit: int
    created_at: str


@app.post("/api/keys/bootstrap", response_model=KeyOut, status_code=201)
def bootstrap_key(req: KeyCreate, db: Session = Depends(get_db)):
    """Create the first API key. Only works when no keys exist yet."""
    existing = db.query(models.ApiKey).first()
    if existing:
        raise HTTPException(status_code=403, detail="Keys already exist. Use POST /api/keys with a valid key.")
    raw, row = create_api_key(db, req.name, req.rate_limit)
    return KeyOut(id=row.id, name=row.name, key=raw, is_active=row.is_active, rate_limit=row.rate_limit, created_at=row.created_at.isoformat())


@app.post("/api/keys", response_model=KeyOut, status_code=201)
def make_key(req: KeyCreate, db: Session = Depends(get_db), _key=Depends(require_key)):
    raw, row = create_api_key(db, req.name, req.rate_limit)
    return KeyOut(id=row.id, name=row.name, key=raw, is_active=row.is_active, rate_limit=row.rate_limit, created_at=row.created_at.isoformat())


@app.get("/api/keys", response_model=List[KeyOut])
def list_keys(db: Session = Depends(get_db), _key=Depends(require_key)):
    rows = db.query(models.ApiKey).order_by(desc(models.ApiKey.created_at)).all()
    return [
        KeyOut(id=r.id, name=r.name, is_active=r.is_active, rate_limit=r.rate_limit or 60, created_at=r.created_at.isoformat())
        for r in rows
    ]


@app.delete("/api/keys/{key_id}", status_code=204)
def revoke_key(key_id: int, db: Session = Depends(get_db), _key=Depends(require_key)):
    row = db.query(models.ApiKey).filter(models.ApiKey.id == key_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Key not found")
    row.is_active = False
    db.commit()


@app.get("/api/keys/{key_id}/usage")
def get_key_usage(key_id: int, db: Session = Depends(get_db), _key=Depends(require_key)):
    row = db.query(models.ApiKey).filter(models.ApiKey.id == key_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Key not found")

    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    one_min_ago = now - timedelta(minutes=1)
    one_hour_ago = now - timedelta(hours=1)
    one_day_ago = now - timedelta(days=1)

    last_minute = db.query(func.count(models.UsageLog.id)).filter(
        models.UsageLog.api_key_id == key_id, models.UsageLog.created_at >= one_min_ago
    ).scalar()
    last_hour = db.query(func.count(models.UsageLog.id)).filter(
        models.UsageLog.api_key_id == key_id, models.UsageLog.created_at >= one_hour_ago
    ).scalar()
    last_day = db.query(func.count(models.UsageLog.id)).filter(
        models.UsageLog.api_key_id == key_id, models.UsageLog.created_at >= one_day_ago
    ).scalar()
    total = db.query(func.count(models.UsageLog.id)).filter(
        models.UsageLog.api_key_id == key_id
    ).scalar()

    top_endpoints = (
        db.query(models.UsageLog.endpoint, func.count(models.UsageLog.id).label("count"))
        .filter(models.UsageLog.api_key_id == key_id)
        .group_by(models.UsageLog.endpoint)
        .order_by(desc("count"))
        .limit(10)
        .all()
    )

    return {
        "key_id": key_id,
        "key_name": row.name,
        "rate_limit": row.rate_limit or 60,
        "usage": {
            "last_minute": last_minute,
            "last_hour": last_hour,
            "last_24h": last_day,
            "total": total,
        },
        "remaining_this_minute": max(0, (row.rate_limit or 60) - last_minute),
        "top_endpoints": {ep: cnt for ep, cnt in top_endpoints},
    }


# ── Plugins (custom tools) ──


class PluginCreate(BaseModel):
    name: str
    description: str
    url: str
    method: str = "POST"
    headers: Optional[dict] = None
    parameters: dict


class PluginUpdate(BaseModel):
    description: Optional[str] = None
    url: Optional[str] = None
    method: Optional[str] = None
    headers: Optional[dict] = None
    parameters: Optional[dict] = None
    is_active: Optional[bool] = None


class PluginOut(BaseModel):
    id: int
    name: str
    description: str
    url: str
    method: str
    has_headers: bool
    parameters: dict
    is_active: bool
    created_at: str


@app.post("/api/plugins", response_model=PluginOut, status_code=201)
def create_plugin(req: PluginCreate, db: Session = Depends(get_db), _key=Depends(require_key)):
    existing = db.query(models.Plugin).filter(models.Plugin.name == req.name).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Plugin '{req.name}' already exists")
    plugin = models.Plugin(
        name=req.name, description=req.description, url=req.url,
        method=req.method.upper(),
        headers_json=json.dumps(req.headers) if req.headers else None,
        parameters_json=json.dumps(req.parameters),
    )
    db.add(plugin)
    db.commit()
    db.refresh(plugin)
    return _plugin_out(plugin)


@app.get("/api/plugins", response_model=List[PluginOut])
def list_plugins(db: Session = Depends(get_db), _key=Depends(require_key)):
    rows = db.query(models.Plugin).order_by(desc(models.Plugin.created_at)).all()
    return [_plugin_out(r) for r in rows]


@app.put("/api/plugins/{name}", response_model=PluginOut)
def update_plugin(name: str, req: PluginUpdate, db: Session = Depends(get_db), _key=Depends(require_key)):
    plugin = db.query(models.Plugin).filter(models.Plugin.name == name).first()
    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin not found")
    if req.description is not None:
        plugin.description = req.description
    if req.url is not None:
        plugin.url = req.url
    if req.method is not None:
        plugin.method = req.method.upper()
    if req.headers is not None:
        plugin.headers_json = json.dumps(req.headers)
    if req.parameters is not None:
        plugin.parameters_json = json.dumps(req.parameters)
    if req.is_active is not None:
        plugin.is_active = req.is_active
    db.commit()
    db.refresh(plugin)
    return _plugin_out(plugin)


@app.delete("/api/plugins/{name}", status_code=204)
def delete_plugin(name: str, db: Session = Depends(get_db), _key=Depends(require_key)):
    plugin = db.query(models.Plugin).filter(models.Plugin.name == name).first()
    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin not found")
    db.delete(plugin)
    db.commit()


def _plugin_out(p) -> PluginOut:
    return PluginOut(
        id=p.id, name=p.name, description=p.description, url=p.url,
        method=p.method, has_headers=bool(p.headers_json),
        parameters=json.loads(p.parameters_json),
        is_active=p.is_active, created_at=p.created_at.isoformat(),
    )


# ── Scheduled tasks ──


class ScheduleCreate(BaseModel):
    name: str
    task: str
    cron: str
    chain_roles: Optional[str] = None


class ScheduleUpdate(BaseModel):
    task: Optional[str] = None
    cron: Optional[str] = None
    chain_roles: Optional[str] = None
    is_active: Optional[bool] = None


class ScheduleOut(BaseModel):
    id: int
    name: str
    task: str
    cron: str
    chain_roles: Optional[str]
    is_active: bool
    last_run_at: Optional[str]
    next_run_at: Optional[str]
    run_count: int
    created_at: str


@app.post("/api/schedules", response_model=ScheduleOut, status_code=201)
def create_schedule(req: ScheduleCreate, db: Session = Depends(get_db), _key=Depends(require_key)):
    from croniter import croniter
    if not croniter.is_valid(req.cron):
        raise HTTPException(status_code=400, detail=f"Invalid cron expression: {req.cron}")
    from scheduler import _compute_next_run
    next_run = _compute_next_run(req.cron)
    sched = models.Schedule(
        name=req.name, task=req.task, cron=req.cron,
        chain_roles=req.chain_roles, next_run_at=next_run,
    )
    db.add(sched)
    db.commit()
    db.refresh(sched)
    return _sched_out(sched)


@app.get("/api/schedules", response_model=List[ScheduleOut])
def list_schedules(db: Session = Depends(get_db), _key=Depends(require_key)):
    rows = db.query(models.Schedule).order_by(desc(models.Schedule.created_at)).all()
    return [_sched_out(r) for r in rows]


@app.put("/api/schedules/{schedule_id}", response_model=ScheduleOut)
def update_schedule(schedule_id: int, req: ScheduleUpdate, db: Session = Depends(get_db), _key=Depends(require_key)):
    sched = db.query(models.Schedule).filter(models.Schedule.id == schedule_id).first()
    if not sched:
        raise HTTPException(status_code=404, detail="Schedule not found")
    if req.task is not None:
        sched.task = req.task
    if req.cron is not None:
        from croniter import croniter
        if not croniter.is_valid(req.cron):
            raise HTTPException(status_code=400, detail=f"Invalid cron expression: {req.cron}")
        sched.cron = req.cron
        from scheduler import _compute_next_run
        sched.next_run_at = _compute_next_run(req.cron)
    if req.chain_roles is not None:
        sched.chain_roles = req.chain_roles
    if req.is_active is not None:
        sched.is_active = req.is_active
    db.commit()
    db.refresh(sched)
    return _sched_out(sched)


@app.delete("/api/schedules/{schedule_id}", status_code=204)
def delete_schedule(schedule_id: int, db: Session = Depends(get_db), _key=Depends(require_key)):
    sched = db.query(models.Schedule).filter(models.Schedule.id == schedule_id).first()
    if not sched:
        raise HTTPException(status_code=404, detail="Schedule not found")
    db.delete(sched)
    db.commit()


@app.post("/api/schedules/{schedule_id}/run")
def run_schedule_now(schedule_id: int, db: Session = Depends(get_db), _key=Depends(require_key)):
    sched = db.query(models.Schedule).filter(models.Schedule.id == schedule_id).first()
    if not sched:
        raise HTTPException(status_code=404, detail="Schedule not found")
    task_row = models.Task(input=f"[scheduled:{sched.name}] {sched.task}", status="pending")
    db.add(task_row)
    db.commit()
    db.refresh(task_row)
    submit_task(task_row.id)
    return {"status": "submitted", "task_id": task_row.id, "schedule": sched.name}


def _sched_out(s) -> ScheduleOut:
    return ScheduleOut(
        id=s.id, name=s.name, task=s.task, cron=s.cron,
        chain_roles=s.chain_roles, is_active=s.is_active,
        last_run_at=s.last_run_at.isoformat() if s.last_run_at else None,
        next_run_at=s.next_run_at.isoformat() if s.next_run_at else None,
        run_count=s.run_count or 0, created_at=s.created_at.isoformat(),
    )


# ── Webhooks ──

VALID_EVENTS = ["task.completed"]


class WebhookCreate(BaseModel):
    name: str
    url: str
    event: str = "task.completed"
    secret: Optional[str] = None


class WebhookUpdate(BaseModel):
    url: Optional[str] = None
    event: Optional[str] = None
    secret: Optional[str] = None
    is_active: Optional[bool] = None


class WebhookOut(BaseModel):
    id: int
    name: str
    url: str
    event: str
    has_secret: bool
    is_active: bool
    created_at: str


@app.post("/api/webhooks", response_model=WebhookOut, status_code=201)
def create_webhook(req: WebhookCreate, db: Session = Depends(get_db), _key=Depends(require_key)):
    if req.event not in VALID_EVENTS:
        raise HTTPException(status_code=400, detail=f"Invalid event. Valid: {VALID_EVENTS}")
    hook = models.Webhook(name=req.name, url=req.url, event=req.event, secret=req.secret)
    db.add(hook)
    db.commit()
    db.refresh(hook)
    return WebhookOut(
        id=hook.id, name=hook.name, url=hook.url, event=hook.event,
        has_secret=bool(hook.secret), is_active=hook.is_active,
        created_at=hook.created_at.isoformat(),
    )


@app.get("/api/webhooks", response_model=List[WebhookOut])
def list_webhooks(db: Session = Depends(get_db), _key=Depends(require_key)):
    rows = db.query(models.Webhook).order_by(desc(models.Webhook.created_at)).all()
    return [
        WebhookOut(
            id=r.id, name=r.name, url=r.url, event=r.event,
            has_secret=bool(r.secret), is_active=r.is_active,
            created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]


@app.put("/api/webhooks/{webhook_id}", response_model=WebhookOut)
def update_webhook(webhook_id: int, req: WebhookUpdate, db: Session = Depends(get_db), _key=Depends(require_key)):
    hook = db.query(models.Webhook).filter(models.Webhook.id == webhook_id).first()
    if not hook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    if req.url is not None:
        hook.url = req.url
    if req.event is not None:
        if req.event not in VALID_EVENTS:
            raise HTTPException(status_code=400, detail=f"Invalid event. Valid: {VALID_EVENTS}")
        hook.event = req.event
    if req.secret is not None:
        hook.secret = req.secret
    if req.is_active is not None:
        hook.is_active = req.is_active
    db.commit()
    db.refresh(hook)
    return WebhookOut(
        id=hook.id, name=hook.name, url=hook.url, event=hook.event,
        has_secret=bool(hook.secret), is_active=hook.is_active,
        created_at=hook.created_at.isoformat(),
    )


@app.delete("/api/webhooks/{webhook_id}", status_code=204)
def delete_webhook(webhook_id: int, db: Session = Depends(get_db), _key=Depends(require_key)):
    hook = db.query(models.Webhook).filter(models.Webhook.id == webhook_id).first()
    if not hook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    db.delete(hook)
    db.commit()


@app.post("/api/webhooks/{webhook_id}/test")
def test_webhook(webhook_id: int, db: Session = Depends(get_db), _key=Depends(require_key)):
    hook = db.query(models.Webhook).filter(models.Webhook.id == webhook_id).first()
    if not hook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    fire_task_completed(db, 0, "Test task from VOREE", "research_v1", "This is a test webhook delivery.", 10)
    return {"status": "sent", "webhook": hook.name, "url": hook.url}


# ── Analytics & export ──


@app.get("/api/stats")
def get_stats(db: Session = Depends(get_db), _key=Depends(require_key)):
    total_tasks = db.query(func.count(models.Task.id)).scalar()
    scored_tasks = db.query(func.count(models.Task.id)).filter(models.Task.score.isnot(None)).scalar()
    avg_score = db.query(func.avg(models.Task.score)).filter(models.Task.score.isnot(None)).scalar()
    total_memories = db.query(func.count(models.Memory.id)).scalar()
    total_sessions = db.query(func.count(models.Session.id)).scalar()
    total_messages = db.query(func.count(models.Message.id)).scalar()

    workflow_counts = (
        db.query(models.Task.workflow, func.count(models.Task.id))
        .group_by(models.Task.workflow)
        .all()
    )
    workflow_breakdown = {w: c for w, c in workflow_counts if w}

    score_dist = (
        db.query(models.Task.score, func.count(models.Task.id))
        .filter(models.Task.score.isnot(None))
        .group_by(models.Task.score)
        .order_by(models.Task.score)
        .all()
    )
    score_distribution = {str(s): c for s, c in score_dist}

    return {
        "tasks": {
            "total": total_tasks,
            "scored": scored_tasks,
            "avg_score": round(float(avg_score), 2) if avg_score else None,
            "workflow_breakdown": workflow_breakdown,
            "score_distribution": score_distribution,
        },
        "memories": {"total": total_memories},
        "sessions": {"total": total_sessions, "total_messages": total_messages},
    }


@app.get("/api/export/tasks")
def export_tasks(
    format: str = Query(default="json", regex="^(json|csv)$"),
    db: Session = Depends(get_db),
    _key=Depends(require_key),
):
    rows = db.query(models.Task).order_by(desc(models.Task.created_at)).all()

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["id", "task", "workflow", "score", "result", "created_at"])
        for r in rows:
            writer.writerow([r.id, r.input, r.workflow, r.score, r.result, r.created_at.isoformat()])
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=voree_tasks.csv"},
        )

    data = [
        {
            "id": r.id,
            "task": r.input,
            "workflow": r.workflow,
            "score": r.score,
            "result": r.result,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
    return Response(
        content=json.dumps(data, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=voree_tasks.json"},
    )


@app.get("/api/export/memories")
def export_memories(
    format: str = Query(default="json", regex="^(json|csv)$"),
    db: Session = Depends(get_db),
    _key=Depends(require_key),
):
    rows = db.query(models.Memory).order_by(desc(models.Memory.created_at)).all()

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["id", "content", "created_at"])
        for r in rows:
            writer.writerow([r.id, r.content, r.created_at.isoformat()])
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=voree_memories.csv"},
        )

    data = [
        {"id": r.id, "content": r.content, "created_at": r.created_at.isoformat()}
        for r in rows
    ]
    return Response(
        content=json.dumps(data, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=voree_memories.json"},
    )


@app.get("/health")
def health():
    """Verify the service is up and the database is reachable."""
    try:
        check_connection()
        db_ok = True
    except Exception as exc:  # surface the failure without crashing the endpoint
        return {"status": "degraded", "database": False, "error": str(exc)}
    return {"status": "ok", "database": db_ok}


@app.get("/")
def dashboard():
    return FileResponse("static/index.html")