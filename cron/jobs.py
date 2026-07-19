"""Job model and storage for the scheduler."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Type


@dataclass
class Job:
    """A scheduled job."""
    name: str
    job_type: str  # e.g., "reminder", "task", "webhook"
    params: Dict[str, Any] = field(default_factory=dict)
    next_run: Optional[datetime] = None
    interval_minutes: Optional[int] = None  # None = one-shot
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: datetime = field(default_factory=datetime.now)
    enabled: bool = True


class JobStorage:
    """Store jobs in the database."""

    def __init__(self, db_path: Optional[str] = None):
        self._db_path = db_path

    def save(self, job: Job) -> None:
        """Save a job to the database."""
        try:
            import sqlite3
            conn = sqlite3.connect(self._db_path or "aiaurum.db")
            conn.execute(
                """CREATE TABLE IF NOT EXISTS scheduled_jobs (
                    id TEXT PRIMARY KEY,
                    name TEXT, job_type TEXT, params TEXT,
                    next_run TEXT, interval_minutes INTEGER,
                    created_at TEXT, enabled INTEGER
                )"""
            )
            conn.execute(
                "INSERT OR REPLACE INTO scheduled_jobs VALUES (?,?,?,?,?,?,?,?)",
                (
                    job.id, job.name, job.job_type, json.dumps(job.params),
                    job.next_run.isoformat() if job.next_run else None,
                    job.interval_minutes,
                    job.created_at.isoformat(),
                    1 if job.enabled else 0,
                ),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            raise RuntimeError(f"Failed to save job: {e}")

    def delete(self, job_id: str) -> bool:
        try:
            import sqlite3
            conn = sqlite3.connect(self._db_path or "aiaurum.db")
            conn.execute("DELETE FROM scheduled_jobs WHERE id = ?", (job_id,))
            conn.commit()
            conn.close()
            return True
        except Exception:
            return False

    def get_due(self, now: datetime) -> List[Job]:
        """Get all jobs that are due to run."""
        try:
            import sqlite3
            conn = sqlite3.connect(self._db_path or "aiaurum.db")
            rows = conn.execute(
                "SELECT * FROM scheduled_jobs WHERE enabled=1 AND next_run <= ?",
                (now.isoformat(),),
            ).fetchall()
            conn.close()
            return [self._row_to_job(r) for r in rows]
        except Exception:
            return []

    def list_all(self) -> List[Job]:
        try:
            import sqlite3
            conn = sqlite3.connect(self._db_path or "aiaurum.db")
            rows = conn.execute("SELECT * FROM scheduled_jobs WHERE enabled=1").fetchall()
            conn.close()
            return [self._row_to_job(r) for r in rows]
        except Exception:
            return []

    def update_next_run(self, job_id: str, next_run: datetime) -> None:
        try:
            import sqlite3
            conn = sqlite3.connect(self._db_path or "aiaurum.db")
            conn.execute(
                "UPDATE scheduled_jobs SET next_run = ? WHERE id = ?",
                (next_run.isoformat(), job_id),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    def _row_to_job(self, row) -> Job:
        return Job(
            id=row[0], name=row[1], job_type=row[2],
            params=json.loads(row[3]) if row[3] else {},
            next_run=datetime.fromisoformat(row[4]) if row[4] else None,
            interval_minutes=row[5],
            created_at=datetime.fromisoformat(row[6]) if row[6] else datetime.now(),
            enabled=bool(row[7]),
        )
