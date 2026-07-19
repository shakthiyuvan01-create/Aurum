"""Scheduler — run jobs at scheduled times.

Background thread that checks every 30 seconds for due jobs
and executes them. Jobs are stored in the database.
"""
from __future__ import annotations

import logging
import sched
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from cron.jobs import Job, JobStorage

logger = logging.getLogger(__name__)


class Scheduler:
    """Background scheduler that runs due jobs."""

    def __init__(self):
        self._storage: Optional[JobStorage] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._handlers: Dict[str, Callable] = {}
        self._tick_interval = 30  # seconds

    def set_storage(self, storage: JobStorage) -> None:
        self._storage = storage

    def register_handler(self, job_type: str, handler: Callable) -> None:
        self._handlers[job_type] = handler

    def add_job(self, job: Job) -> str:
        if self._storage:
            self._storage.save(job)
        return job.id

    def remove_job(self, job_id: str) -> bool:
        if self._storage:
            return self._storage.delete(job_id)
        return False

    def list_jobs(self) -> List[Job]:
        if self._storage:
            return self._storage.list_all()
        return []

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
            logger.info("Scheduler started (tick every %ds)", self._tick_interval)

    def stop(self) -> None:
        with self._lock:
            self._running = False
            logger.info("Scheduler stopped")

    def _run_loop(self) -> None:
        while self._running:
            try:
                self._tick()
            except Exception as e:
                logger.error("Scheduler tick error: %s", e)
            time.sleep(self._tick_interval)

    def _tick(self) -> None:
        if not self._storage:
            return
        now = datetime.now()
        due = self._storage.get_due(now)
        for job in due:
            try:
                self._execute_job(job)
            except Exception as e:
                logger.error("Job %s failed: %s", job.id, e)

    def _execute_job(self, job: Job) -> None:
        logger.info("Executing job %s (%s)", job.id, job.name)
        if job.job_type in self._handlers:
            try:
                self._handlers[job.job_type](job)
            except Exception as e:
                logger.error("Handler for job %s failed: %s", job.id, e)
        if job.interval_minutes:
            # Recurring: update next run
            from datetime import timedelta
            job.next_run = datetime.now() + timedelta(minutes=job.interval_minutes)
            if job.next_run:
                if self._storage:
                    self._storage.update_next_run(job.id, job.next_run)
        else:
            # One-shot: remove
            if self._storage:
                self._storage.delete(job.id)


# Global singleton
_scheduler: Optional[Scheduler] = None
_sched_lock = threading.Lock()


def get_scheduler() -> Scheduler:
    global _scheduler
    if _scheduler is None:
        with _sched_lock:
            if _scheduler is None:
                _scheduler = Scheduler()
    return _scheduler
