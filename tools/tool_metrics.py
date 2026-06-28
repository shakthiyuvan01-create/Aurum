"""
tools/tool_metrics.py — Per-tool SQLite performance & reliability metrics
=========================================================================
Tracks for every tool:
    success_count    — total successful calls
    failure_count    — total failed calls
    avg_runtime_ms   — running average of wall-clock runtime
    last_failure_ts  — UNIX timestamp of most recent failure (or 0)
    cost_tier        — "free" | "cheap" | "expensive" (set via COST_TIERS)

Public API
----------
    record_call(name, success, runtime_ms)  — record one execution result
    get_metrics(name=None)                  — return dict (or all) of metrics
    should_warn(name)                       — True if >3 failures in last hour
    reset_metrics(name)                     — zero-out one tool's counters
"""
from __future__ import annotations
import os, sqlite3, time, logging, threading
from contextlib import contextmanager

log = logging.getLogger("tools.metrics")

# ── DB path ──────────────────────────────────────────────────────────────────
_HERE    = os.path.dirname(os.path.abspath(__file__))
_DB_PATH = os.path.join(os.path.dirname(_HERE), "tool_metrics.db")
_lock    = threading.Lock()

# ── Cost tiers (override by setting env TOOL_COST_<TOOLNAME>=expensive etc.) ──
COST_TIERS: dict[str, str] = {
    # free — no API key, local only
    "weather":        "cheap",
    "web_search":     "cheap",
    "news":           "cheap",
    "youtube_search": "cheap",
    "wikipedia":      "free",
    "calculator":     "free",
    "reminders":      "free",
    "scheduler":      "free",
    "code_runner":    "free",
    # expensive — uses paid APIs
    "image_gen":      "expensive",
    "vision":         "expensive",
    "browser":        "expensive",
    "workflow":       "expensive",
}

_WARN_THRESHOLD    = 3        # failures before warning
_WARN_WINDOW_SECS  = 3600     # look back 1 hour for recent failures


# ── Schema ───────────────────────────────────────────────────────────────────
_SCHEMA = """
CREATE TABLE IF NOT EXISTS tool_metrics (
    name            TEXT PRIMARY KEY,
    success_count   INTEGER  DEFAULT 0,
    failure_count   INTEGER  DEFAULT 0,
    avg_runtime_ms  REAL     DEFAULT 0.0,
    last_failure_ts REAL     DEFAULT 0.0,
    cost_tier       TEXT     DEFAULT 'free',
    updated_at      REAL     DEFAULT 0.0
);
CREATE TABLE IF NOT EXISTS tool_failure_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name      TEXT    NOT NULL,
    ts        REAL    NOT NULL,
    runtime_ms REAL   NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fail_name_ts ON tool_failure_log(name, ts);
"""


@contextmanager
def _db():
    with _lock:
        con = sqlite3.connect(_DB_PATH, timeout=10)
        con.row_factory = sqlite3.Row
        try:
            con.executescript(_SCHEMA)
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()


def _ensure_row(con: sqlite3.Connection, name: str):
    """Insert a default row if not present."""
    tier = COST_TIERS.get(name, "free")
    # honour env override
    env_key = "TOOL_COST_" + name.upper()
    tier = os.getenv(env_key, tier)
    con.execute(
        "INSERT OR IGNORE INTO tool_metrics(name, cost_tier, updated_at) VALUES(?,?,?)",
        (name, tier, time.time()),
    )


# ── Public API ────────────────────────────────────────────────────────────────

def record_call(name: str, success: bool, runtime_ms: float) -> None:
    """Record the outcome of a single tool call."""
    now = time.time()
    try:
        with _db() as con:
            _ensure_row(con, name)
            if success:
                con.execute("""
                    UPDATE tool_metrics
                    SET success_count = success_count + 1,
                        avg_runtime_ms = (avg_runtime_ms * success_count + ?) / (success_count + 1),
                        updated_at = ?
                    WHERE name = ?
                """, (runtime_ms, now, name))
            else:
                con.execute("""
                    UPDATE tool_metrics
                    SET failure_count = failure_count + 1,
                        last_failure_ts = ?,
                        updated_at = ?
                    WHERE name = ?
                """, (now, now, name))
                # append to failure log for time-window queries
                con.execute(
                    "INSERT INTO tool_failure_log(name, ts, runtime_ms) VALUES(?,?,?)",
                    (name, now, runtime_ms),
                )
    except Exception as e:
        log.debug("record_call db error: %s", e)


def get_metrics(name: str | None = None) -> dict:
    """
    Return metrics for one tool (dict) or all tools (dict[name -> dict]).
    Returns empty dict if tool not found.
    """
    try:
        with _db() as con:
            if name:
                _ensure_row(con, name)
                row = con.execute(
                    "SELECT * FROM tool_metrics WHERE name=?", (name,)
                ).fetchone()
                return dict(row) if row else {}
            else:
                rows = con.execute("SELECT * FROM tool_metrics").fetchall()
                return {r["name"]: dict(r) for r in rows}
    except Exception as e:
        log.debug("get_metrics db error: %s", e)
        return {}


def should_warn(name: str) -> bool:
    """Return True if this tool has ≥ _WARN_THRESHOLD failures in the last hour."""
    try:
        with _db() as con:
            cutoff = time.time() - _WARN_WINDOW_SECS
            row = con.execute(
                "SELECT COUNT(*) AS cnt FROM tool_failure_log WHERE name=? AND ts>=?",
                (name, cutoff),
            ).fetchone()
            return (row["cnt"] if row else 0) >= _WARN_THRESHOLD
    except Exception as e:
        log.debug("should_warn db error: %s", e)
        return False


def reset_metrics(name: str) -> None:
    """Zero-out counters for a tool (useful after a tool is fixed/reloaded)."""
    try:
        with _db() as con:
            con.execute("""
                UPDATE tool_metrics
                SET success_count=0, failure_count=0, avg_runtime_ms=0.0,
                    last_failure_ts=0.0, updated_at=?
                WHERE name=?
            """, (time.time(), name))
            con.execute(
                "DELETE FROM tool_failure_log WHERE name=?", (name,)
            )
    except Exception as e:
        log.debug("reset_metrics db error: %s", e)
