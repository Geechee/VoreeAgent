"""Background task worker — processes tasks asynchronously."""
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from agent import run_agent
from critic import critique
from db import SessionLocal
from memory import retrieve_memories, store_memory
from rag import retrieve_chunks
from webhooks import fire_task_completed
from workflows import select_workflow

import models

logger = logging.getLogger("voree.worker")
_executor = ThreadPoolExecutor(max_workers=3)


def _process_task(task_id: int):
    """Run the full pipeline for a task in the background."""
    db = SessionLocal()
    try:
        task_row = db.query(models.Task).filter(models.Task.id == task_id).first()
        if not task_row:
            return

        task_row.status = "running"
        db.commit()

        workflow = select_workflow(task_row.input, db)
        task_row.workflow = workflow
        db.commit()

        memories = retrieve_memories(db, task_row.input, k=5)
        doc_chunks = retrieve_chunks(db, task_row.input, k=5)
        result, tools_log = run_agent(
            task_row.input, workflow, memories, db=db,
            doc_chunks=doc_chunks or None,
        )

        review = critique(task_row.input, result)
        score = review["score"]

        if score < 7:
            result, tools_log = run_agent(
                task_row.input, workflow, memories, db=db,
                doc_chunks=doc_chunks or None,
            )
            review = critique(task_row.input, result)
            score = review["score"]

        task_row.result = result
        task_row.score = score
        task_row.status = "completed"
        task_row.completed_at = datetime.now(timezone.utc)
        db.commit()

        critique_row = models.Critique(
            task_id=task_row.id, score=score, feedback=review["feedback"]
        )
        db.add(critique_row)
        db.commit()

        store_memory(db, f"Task: {task_row.input} | Result summary: {result[:200]}")
        fire_task_completed(db, task_row.id, task_row.input, workflow, result, score)

        logger.info(f"Task {task_id} completed, score={score}")

    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}")
        task_row = db.query(models.Task).filter(models.Task.id == task_id).first()
        if task_row:
            task_row.status = "failed"
            task_row.error = str(e)
            task_row.completed_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()


def submit_task(task_id: int):
    """Submit a task for background processing."""
    _executor.submit(_process_task, task_id)
