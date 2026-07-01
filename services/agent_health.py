"""
services/agent_health.py — Agent health monitoring.

Tracks per-agent: average latency, success/fail/timeout rates, token usage.
The CEO uses health scores to avoid routing work to degraded agents.

Usage:
    from services.agent_health import health

    # Record a result after an agent call
    health.record("programmer", latency_ms=1200, success=True, tokens=450)

    # Get health score for an agent (1.0 = healthy, 0.0 = dead)
    score = health.score("programmer")   # e.g. 0.91

    # Get the healthiest agent from a ranked list
    best = health.pick_healthy(["programmer", "debugger", "researcher"])
"""
from __future__ import annotations

import logging
import os
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

log = logging.getLogger("services.agent_health")

_DB = str(Path(os.path.abspath(__file__)).parent.parent / "aiaurum.db")

# Thresholds
_TIMEOUT_MS         = 45_000   # calls > 45 s are considered timeouts
_UNHEALTHY_SCORE    = 0.40     # below this, CEO avoids the agent
_WINDOW_MINUTES     = 60       # rolling window for rate calculations
_MIN_CALLS_FOR_RATE = 3        # need at least N calls before penalising


@contextmanager
def _conn():
    con = sqlite3.connect(_DB)
    con.row_factory = sqlite3.Row
    con.execute("""
        CREATE TABLE IF NOT EXISTS agent_health_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_name  TEXT    NOT NULL,
            latency_ms  INTEGER DEFAULT 0,
            success     INTEGER DEFAULT 1,   -- 1=success 0=fail
            timed_out   INTEGER DEFAULT 0,
            tokens_used INTEGER DEFAULT 0,
            recorded_at INTEGER DEFAULT (strftime('%s','now'))
        )
    """)
    con.execute("CREATE INDEX IF NOT EXISTS idx_ahl_agent ON agent_health_log(agent_name, recorded_at)")
    con.commit()
    try:
        yield con
        con.commit()
    finally:
        con.close()


@dataclass
class AgentStats:
    agent_name:    str
    call_count:    int
    success_count: int
    fail_count:    int
    timeout_count: int
    avg_latency_ms:float
    p95_latency_ms:float
    total_tokens:  int
    health_score:  float   # 0.0–1.0
    is_healthy:    bool


class AgentHealthMonitor:

    def record(
        self,
        agent_name: str,
        latency_ms: int  = 0,
        success:    bool = True,
        tokens:     int  = 0,
        timed_out:  bool = False,
    ) -> None:
        with _conn() as con:
            con.execute(
                "INSERT INTO agent_health_log(agent_name,latency_ms,success,timed_out,tokens_used) "
                "VALUES (?,?,?,?,?)",
                (agent_name, latency_ms, int(success), int(timed_out), tokens),
            )

    def stats(self, agent_name: str, window_minutes: int = _WINDOW_MINUTES) -> AgentStats:
        since = int(time.time()) - window_minutes * 60
        with _conn() as con:
            rows = con.execute(
                "SELECT latency_ms, success, timed_out, tokens_used "
                "FROM agent_health_log "
                "WHERE agent_name=? AND recorded_at >= ? "
                "ORDER BY recorded_at DESC LIMIT 200",
                (agent_name, since),
            ).fetchall()

        if not rows:
            return AgentStats(
                agent_name    = agent_name,
                call_count    = 0,
                success_count = 0,
                fail_count    = 0,
                timeout_count = 0,
                avg_latency_ms= 0.0,
                p95_latency_ms= 0.0,
                total_tokens  = 0,
                health_score  = 1.0,
                is_healthy    = True,
            )

        latencies     = [r["latency_ms"] for r in rows]
        success_count = sum(1 for r in rows if r["success"])
        fail_count    = sum(1 for r in rows if not r["success"])
        timeout_count = sum(1 for r in rows if r["timed_out"])
        total_tokens  = sum(r["tokens_used"] for r in rows)
        call_count    = len(rows)

        avg_lat  = sum(latencies) / call_count
        sorted_l = sorted(latencies)
        p95_idx  = max(0, int(call_count * 0.95) - 1)
        p95_lat  = sorted_l[p95_idx]

        score = self._compute_score(
            call_count, success_count, fail_count, timeout_count, avg_lat
        )

        return AgentStats(
            agent_name    = agent_name,
            call_count    = call_count,
            success_count = success_count,
            fail_count    = fail_count,
            timeout_count = timeout_count,
            avg_latency_ms= round(avg_lat, 1),
            p95_latency_ms= round(p95_lat, 1),
            total_tokens  = total_tokens,
            health_score  = round(score, 3),
            is_healthy    = score >= _UNHEALTHY_SCORE,
        )

    def score(self, agent_name: str) -> float:
        return self.stats(agent_name).health_score

    def _compute_score(
        self,
        call_count:    int,
        success_count: int,
        fail_count:    int,
        timeout_count: int,
        avg_lat_ms:    float,
    ) -> float:
        if call_count < _MIN_CALLS_FOR_RATE:
            return 1.0   # not enough data — assume healthy

        # Success rate (0–1)
        success_rate = success_count / call_count

        # Latency penalty: 0 at 0ms, 1 at 30s
        latency_penalty = min(avg_lat_ms / 30_000, 1.0)

        # Timeout penalty
        timeout_rate = timeout_count / call_count

        score = (
            success_rate * 0.60
            - latency_penalty * 0.25
            - timeout_rate  * 0.15
        )
        return max(0.0, min(1.0, score))

    def pick_healthy(self, candidates: list[str]) -> str:
        """
        From a ranked list of candidate agent names, return the first
        that is healthy. Falls back to the first candidate if all are sick.
        """
        for name in candidates:
            if self.score(name) >= _UNHEALTHY_SCORE:
                return name
        log.warning("All candidates unhealthy: %s — using %s anyway", candidates, candidates[0])
        return candidates[0]

    def all_stats(self, agent_names: list[str] = None) -> list[dict]:
        if not agent_names:
            # Get distinct agent names from DB
            with _conn() as con:
                rows = con.execute(
                    "SELECT DISTINCT agent_name FROM agent_health_log"
                ).fetchall()
            agent_names = [r["agent_name"] for r in rows]

        result = []
        for name in agent_names:
            s = self.stats(name)
            result.append({
                "agent_name":    s.agent_name,
                "call_count":    s.call_count,
                "success_count": s.success_count,
                "fail_count":    s.fail_count,
                "timeout_count": s.timeout_count,
                "avg_latency_ms":s.avg_latency_ms,
                "p95_latency_ms":s.p95_latency_ms,
                "total_tokens":  s.total_tokens,
                "health_score":  s.health_score,
                "is_healthy":    s.is_healthy,
            })
        return sorted(result, key=lambda x: -x["health_score"])


# ── Singleton ─────────────────────────────────────────────────────────────────
health = AgentHealthMonitor()
