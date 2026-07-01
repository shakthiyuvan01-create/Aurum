"""
services/task_queue.py — Background task queue.
Tries RQ (Redis) first; falls back to ThreadPoolExecutor for environments
without Redis (e.g. Render free tier).
"""
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor

log = logging.getLogger("services.task_queue")

# In-memory job store (fallback mode only)
_jobs: dict[str, dict] = {}

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="bg-task")

# Try to initialise RQ + Redis
try:
    from redis import Redis
    from rq import Queue as _RQQueue
    _redis = Redis.from_url(
        __import__("os").getenv("REDIS_URL", "redis://localhost:6379/0"),
        socket_connect_timeout=2,
    )
    _redis.ping()
    _rq = _RQQueue(connection=_redis)
    _USE_RQ = True
    log.info("Task queue: RQ + Redis")
except Exception:
    _rq = None
    _USE_RQ = False
    log.info("Task queue: ThreadPoolExecutor (Redis unavailable)")


def enqueue(fn, *args, **kwargs) -> str:
    """
    Enqueue a callable. Returns job_id (str).
    Track status with get_status(job_id).
    """
    job_id = uuid.uuid4().hex[:12]

    if _USE_RQ and _rq:
        try:
            job = _rq.enqueue(fn, *args, job_id=job_id, **kwargs)
            return job.id
        except Exception as e:
            log.warning("RQ enqueue failed (%s), falling back to thread", e)

    # Thread fallback
    _jobs[job_id] = {"status": "queued", "result": None, "error": None}

    def _run():
        _jobs[job_id]["status"] = "started"
        try:
            result = fn(*args, **kwargs)
            _jobs[job_id].update({"status": "finished", "result": result})
        except Exception as e:
            _jobs[job_id].update({"status": "failed", "error": str(e)})
            log.error("bg-task %s failed: %s", job_id, e)

    _executor.submit(_run)
    return job_id


def get_status(job_id: str) -> dict:
    """Returns {status, result, error}. status: queued/started/finished/failed/unknown"""
    if _USE_RQ and _rq:
        try:
            from rq.job import Job
            job = Job.fetch(job_id, connection=_redis)
            return {
                "status": job.get_status().value,
                "result": job.result,
                "error":  str(job.exc_info) if job.exc_info else None,
            }
        except Exception:
            pass
    return _jobs.get(job_id, {"status": "unknown", "result": None, "error": None})
