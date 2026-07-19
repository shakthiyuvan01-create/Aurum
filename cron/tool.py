"""Scheduler tool — high-level interface for scheduling jobs."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from cron.jobs import Job, JobStorage
from cron.scheduler import get_scheduler

logger = logging.getLogger(__name__)


def schedule_once(
    name: str,
    job_type: str,
    params: Dict[str, Any],
    delay_minutes: float = 0,
    at_time: Optional[datetime] = None,
) -> str:
    """Schedule a one-shot job."""
    scheduler = get_scheduler()
    if not at_time:
        at_time = datetime.now() + timedelta(minutes=delay_minutes)
    job = Job(name=name, job_type=job_type, params=params, next_run=at_time)
    return scheduler.add_job(job)


def schedule_recurring(
    name: str,
    job_type: str,
    params: Dict[str, Any],
    interval_minutes: int,
    start_now: bool = False,
) -> str:
    """Schedule a recurring job."""
    scheduler = get_scheduler()
    next_run = datetime.now() if start_now else datetime.now() + timedelta(minutes=interval_minutes)
    job = Job(
        name=name, job_type=job_type, params=params,
        next_run=next_run, interval_minutes=interval_minutes,
    )
    return scheduler.add_job(job)


def cancel_job(job_id: str) -> bool:
    return get_scheduler().remove_job(job_id)


def list_scheduled_jobs() -> List[Dict[str, Any]]:
    return [
        {
            "id": j.id, "name": j.name, "type": j.job_type,
            "next_run": j.next_run.isoformat() if j.next_run else None,
            "interval_minutes": j.interval_minutes,
            "enabled": j.enabled,
        }
        for j in get_scheduler().list_jobs()
    ]


def start_scheduler(db_path: Optional[str] = None):
    """Initialize and start the scheduler background thread."""
    scheduler = get_scheduler()
    storage = JobStorage(db_path=db_path)
    scheduler.set_storage(storage)

    # Register default handlers
    scheduler.register_handler("log", lambda j: logger.info("Job %s triggered: %s", j.name, j.params))
    scheduler.register_handler("reminder", lambda j: logger.info("REMINDER: %s", j.params.get("text", j.name)))

    scheduler.start()
    return scheduler
