"""
services/tracer.py — Distributed-style request tracing.

Every top-level request gets a trace_id.  Each sub-operation (planner, agent,
tool call, memory lookup) is a Span inside that trace.  The full execution
graph is stored in SQLite and queryable via the /traces API.

Usage:
    from services.tracer import tracer

    # Start a trace (one per user request)
    trace_id = tracer.start_trace(username="yuvan", description="Solar BESS question")

    # Open a span when an operation starts
    span_id = tracer.start_span(trace_id, name="planner", kind="agent")

    # ... do the work ...

    # Close the span with result metadata
    tracer.end_span(span_id, metadata={"steps": 4, "model": "gpt-4o-mini"})

    # Mark trace complete
    tracer.end_trace(trace_id, status="ok")

    # Retrieve full trace
    trace = tracer.get_trace(trace_id)
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

log = logging.getLogger("services.tracer")

_DB = str(Path(os.path.abspath(__file__)).parent.parent / "aiaurum.db")


@contextmanager
def _conn():
    con = sqlite3.connect(_DB)
    con.row_factory = sqlite3.Row
    con.executescript("""
    CREATE TABLE IF NOT EXISTS traces (
        trace_id    TEXT PRIMARY KEY,
        username    TEXT NOT NULL,
        description TEXT DEFAULT '',
        status      TEXT DEFAULT 'running',
        started_at  REAL NOT NULL,
        ended_at    REAL DEFAULT 0,
        duration_ms INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS spans (
        span_id     TEXT PRIMARY KEY,
        trace_id    TEXT NOT NULL,
        parent_id   TEXT DEFAULT '',
        name        TEXT NOT NULL,
        kind        TEXT DEFAULT 'internal',
        status      TEXT DEFAULT 'running',
        started_at  REAL NOT NULL,
        ended_at    REAL DEFAULT 0,
        duration_ms INTEGER DEFAULT 0,
        metadata    TEXT DEFAULT '{}'
    );
    CREATE INDEX IF NOT EXISTS idx_spans_trace ON spans(trace_id);
    CREATE INDEX IF NOT EXISTS idx_traces_user ON traces(username, started_at);
    """)
    con.commit()
    try:
        yield con
        con.commit()
    finally:
        con.close()


@dataclass
class TraceSpan:
    span_id:    str
    trace_id:   str
    parent_id:  str
    name:       str
    kind:       str
    status:     str
    started_at: float
    ended_at:   float
    duration_ms:int
    metadata:   dict


class Tracer:

    # ── Trace lifecycle ───────────────────────────────────────────────────────
    def start_trace(
        self,
        username:    str = "system",
        description: str = "",
        trace_id:    str = None,
    ) -> str:
        tid = trace_id or uuid.uuid4().hex[:16]
        with _conn() as con:
            con.execute(
                "INSERT INTO traces(trace_id,username,description,started_at) VALUES(?,?,?,?)",
                (tid, username, description, time.time()),
            )
        return tid

    def end_trace(self, trace_id: str, status: str = "ok") -> None:
        now = time.time()
        with _conn() as con:
            row = con.execute("SELECT started_at FROM traces WHERE trace_id=?", (trace_id,)).fetchone()
            if row:
                dur = int((now - row["started_at"]) * 1000)
                con.execute(
                    "UPDATE traces SET ended_at=?, duration_ms=?, status=? WHERE trace_id=?",
                    (now, dur, status, trace_id),
                )

    # ── Span lifecycle ────────────────────────────────────────────────────────
    def start_span(
        self,
        trace_id:  str,
        name:      str,
        kind:      str = "internal",
        parent_id: str = "",
        metadata:  dict = None,
    ) -> str:
        sid = uuid.uuid4().hex[:12]
        with _conn() as con:
            con.execute(
                "INSERT INTO spans(span_id,trace_id,parent_id,name,kind,started_at,metadata) "
                "VALUES(?,?,?,?,?,?,?)",
                (sid, trace_id, parent_id, name, kind,
                 time.time(), json.dumps(metadata or {})),
            )
        return sid

    def end_span(
        self,
        span_id:  str,
        status:   str  = "ok",
        metadata: dict = None,
    ) -> None:
        now = time.time()
        with _conn() as con:
            row = con.execute("SELECT started_at, metadata FROM spans WHERE span_id=?", (span_id,)).fetchone()
            if row:
                dur          = int((now - row["started_at"]) * 1000)
                existing_meta = json.loads(row["metadata"] or "{}")
                if metadata:
                    existing_meta.update(metadata)
                con.execute(
                    "UPDATE spans SET ended_at=?, duration_ms=?, status=?, metadata=? WHERE span_id=?",
                    (now, dur, status, json.dumps(existing_meta), span_id),
                )

    def add_event(self, trace_id: str, name: str, metadata: dict = None) -> str:
        """Add a zero-duration event span (log point in a trace)."""
        sid = self.start_span(trace_id, name=name, kind="event", metadata=metadata)
        self.end_span(sid, status="ok")
        return sid

    # ── Query ─────────────────────────────────────────────────────────────────
    def get_trace(self, trace_id: str) -> Optional[dict]:
        with _conn() as con:
            trace_row = con.execute("SELECT * FROM traces WHERE trace_id=?", (trace_id,)).fetchone()
            if not trace_row:
                return None
            trace = dict(trace_row)
            spans = con.execute(
                "SELECT * FROM spans WHERE trace_id=? ORDER BY started_at ASC", (trace_id,)
            ).fetchall()
            trace["spans"] = [
                {**dict(s), "metadata": json.loads(s["metadata"] or "{}")}
                for s in spans
            ]
        return trace

    def list_traces(self, username: str, limit: int = 20) -> list[dict]:
        with _conn() as con:
            rows = con.execute(
                "SELECT trace_id,description,status,started_at,duration_ms "
                "FROM traces WHERE username=? ORDER BY started_at DESC LIMIT ?",
                (username, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def build_graph(self, trace_id: str) -> dict:
        """
        Return a DAG suitable for front-end visualisation.
        nodes: [{id, label, kind, duration_ms, status}]
        edges: [{from, to}]
        """
        trace = self.get_trace(trace_id)
        if not trace:
            return {"nodes": [], "edges": []}

        nodes = []
        edges = []
        span_ids = set()

        for s in trace["spans"]:
            nodes.append({
                "id":         s["span_id"],
                "label":      s["name"],
                "kind":       s["kind"],
                "duration_ms":s["duration_ms"],
                "status":     s["status"],
            })
            span_ids.add(s["span_id"])

        for s in trace["spans"]:
            pid = s.get("parent_id", "")
            if pid and pid in span_ids:
                edges.append({"from": pid, "to": s["span_id"]})

        return {"trace_id": trace_id, "nodes": nodes, "edges": edges,
                "total_ms": trace.get("duration_ms", 0)}

    # ── Context manager helper ─────────────────────────────────────────────────
    def span(self, trace_id: str, name: str, kind: str = "internal", metadata: dict = None):
        """Use as context manager:  with tracer.span(tid, "planner"): ..."""
        return _SpanContext(self, trace_id, name, kind, metadata)


class _SpanContext:
    def __init__(self, tracer: Tracer, trace_id: str, name: str, kind: str, metadata: dict):
        self._tracer   = tracer
        self._trace_id = trace_id
        self._name     = name
        self._kind     = kind
        self._metadata = metadata or {}
        self._span_id  = None

    def __enter__(self) -> str:
        self._span_id = self._tracer.start_span(
            self._trace_id, self._name, self._kind, metadata=self._metadata
        )
        return self._span_id

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        status = "error" if exc_type else "ok"
        self._tracer.end_span(self._span_id, status=status)
        return False   # don't suppress exceptions


# ── Singleton ─────────────────────────────────────────────────────────────────
tracer = Tracer()
