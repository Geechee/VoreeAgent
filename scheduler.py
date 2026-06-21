"""Cron-style task scheduler — checks schedules every 60 seconds."""
import logging
import threading
import time
from datetime import datetime, timezone

from croniter import croniter

from db import SessionLocal
from models import Schedule, Task
from worker import submit_task

logger = logging.getLogger("voree.scheduler")
_running = False


def _compute_next_run(cron_expr: str) -> datetime:
    now = datetime.now(timezone.utc)
    return croniter(cron_expr, now).get_next(datetime)


def _tick():
    """Check all active schedules and fire any that are due."""
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        schedules = db.query(Schedule).filter(Schedule.is_active == True).all()

        for sched in schedules:
            if sched.next_run_at is None:
                sched.next_run_at = _compute_next_run(sched.cron)
                db.commit()
                continue

            next_run = sched.next_run_at
            if next_run.tzinfo is None:
                from datetime import timezone as tz
                next_run = next_run.replace(tzinfo=tz.utc)

            if now >= next_run:
                logger.info(f"Firing schedule '{sched.name}': {sched.task[:50]}")

                task_row = Task(
                    input=f"[scheduled:{sched.name}] {sched.task}",
                    status="pending",
                )
                db.add(task_row)
                db.commit()
                db.refresh(task_row)

                submit_task(task_row.id)

                sched.last_run_at = now
                sched.next_run_at = _compute_next_run(sched.cron)
                sched.run_count = (sched.run_count or 0) + 1
                db.commit()

    except Exception as e:
        logger.error(f"Scheduler tick error: {e}")
    finally:
        db.close()


def _loop():
    global _running
    while _running:
        _tick()
        time.sleep(60)


def start_scheduler():
    global _running
    if _running:
        return
    _running = True
    t = threading.Thread(target=_loop, daemon=True)
    t.start()
    logger.info("Scheduler started")


def stop_scheduler():
    global _running
    _running = False
