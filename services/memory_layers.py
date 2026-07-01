"""
services/memory_layers.py — 5-tier memory architecture.

Tier 1  WorkingMemory    — in-process dict, seconds/minutes, auto-expires
Tier 2  ConversationMemory — SQLite, keyed by chat_id, days
Tier 3  KnowledgeGraph   — NetworkX + SQLite, months (wraps tools/knowledge_graph.py)
Tier 4  VectorMemory     — ChromaDB semantic search (wraps vector_memory.py)
Tier 5  Archive          — cold SQLite store for old conversations, indefinite

Unified interface:

    from services.memory_layers import mem

    # Write
    mem.working.set("draft_code", code_str, ttl_seconds=300)
    mem.conversation.append(username, chat_id, role, text)
    mem.knowledge.add_relation(username, "Python", "used_in", "Flask")
    mem.vector.store(username, user_msg, ai_reply, chat_id)
    mem.archive.store(username, chat_id, messages_list)

    # Read
    val  = mem.working.get("draft_code")
    msgs = mem.conversation.get(username, chat_id, limit=20)
    path = mem.knowledge.path(username, "Python", "Web")
    hits = mem.vector.retrieve(username, query, n=3)
    old  = mem.archive.search(username, "solar BESS")
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger("services.memory")
_DB = str(Path(os.path.abspath(__file__)).parent.parent / "aiaurum.db")


@contextmanager
def _conn(db: str = _DB):
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    try:
        yield con
        con.commit()
    finally:
        con.close()


# ── Tier 1: Working Memory ────────────────────────────────────────────────────
class WorkingMemory:
    """
    Fast in-process key/value store.
    Each entry has a TTL (default 5 minutes). Stale entries are lazily evicted.
    Typical use: hold intermediate results between agent steps within one request.
    """
    _DEFAULT_TTL = 300   # seconds

    def __init__(self) -> None:
        self._store: dict[str, dict] = {}
        self._lock  = threading.Lock()

    def set(self, key: str, value: Any, ttl_seconds: int = _DEFAULT_TTL) -> None:
        with self._lock:
            self._store[key] = {"value": value, "expires": time.time() + ttl_seconds}

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return default
            if time.time() > entry["expires"]:
                del self._store[key]
                return default
            return entry["value"]

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def keys(self) -> list[str]:
        now = time.time()
        with self._lock:
            return [k for k, v in self._store.items() if v["expires"] > now]

    def purge_expired(self) -> int:
        now = time.time()
        with self._lock:
            expired = [k for k, v in self._store.items() if v["expires"] <= now]
            for k in expired:
                del self._store[k]
        return len(expired)


# ── Tier 2: Conversation Memory ───────────────────────────────────────────────
class ConversationMemory:
    """
    Short-to-medium term: stores individual messages in SQLite.
    Messages older than RETENTION_DAYS are moved to Archive automatically.
    """
    RETENTION_DAYS = 30

    def _ensure(self) -> None:
        with _conn() as con:
            con.executescript("""
            CREATE TABLE IF NOT EXISTS conv_memory (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                username   TEXT    NOT NULL,
                chat_id    TEXT    NOT NULL,
                role       TEXT    NOT NULL,
                content    TEXT    NOT NULL,
                tokens     INTEGER DEFAULT 0,
                created_at INTEGER DEFAULT (strftime('%s','now'))
            );
            CREATE INDEX IF NOT EXISTS idx_cm_user_chat ON conv_memory(username, chat_id);
            CREATE INDEX IF NOT EXISTS idx_cm_time ON conv_memory(created_at);
            """)

    def append(self, username: str, chat_id: str, role: str,
               content: str, tokens: int = 0) -> None:
        self._ensure()
        with _conn() as con:
            con.execute(
                "INSERT INTO conv_memory(username,chat_id,role,content,tokens) VALUES(?,?,?,?,?)",
                (username, chat_id, role, content[:4000], tokens),
            )

    def get(self, username: str, chat_id: str, limit: int = 20) -> list[dict]:
        self._ensure()
        with _conn() as con:
            rows = con.execute(
                "SELECT role,content,created_at FROM conv_memory "
                "WHERE username=? AND chat_id=? ORDER BY created_at DESC LIMIT ?",
                (username, chat_id, limit),
            ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def search(self, username: str, query: str, limit: int = 10) -> list[dict]:
        self._ensure()
        q = f"%{query}%"
        with _conn() as con:
            rows = con.execute(
                "SELECT chat_id,role,content,created_at FROM conv_memory "
                "WHERE username=? AND content LIKE ? ORDER BY created_at DESC LIMIT ?",
                (username, q, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def archive_old(self, username: str, archive: "ArchiveMemory") -> int:
        cutoff = int(time.time()) - self.RETENTION_DAYS * 86400
        self._ensure()
        with _conn() as con:
            rows = con.execute(
                "SELECT * FROM conv_memory WHERE username=? AND created_at < ?",
                (username, cutoff),
            ).fetchall()
            if rows:
                archive.bulk_store(username, [dict(r) for r in rows])
                ids = tuple(r["id"] for r in rows)
                con.execute(
                    f"DELETE FROM conv_memory WHERE id IN ({','.join('?' for _ in ids)})", ids
                )
        return len(rows)


# ── Tier 3: Knowledge Graph Memory ───────────────────────────────────────────
class KnowledgeGraphMemory:
    """
    Long-term structured knowledge: entities + directed relationships.
    Wraps the existing tools/knowledge_graph.py logic directly.
    """

    def add_entity(self, username: str, name: str, entity_type: str = "") -> dict:
        from tools.knowledge_graph import run
        return run(action="add_entity", entity=name, entity_type=entity_type, username=username)

    def add_relation(self, username: str, source: str, relation: str, target: str) -> dict:
        from tools.knowledge_graph import run
        return run(action="add_relation", source=source, relation=relation, target=target, username=username)

    def query(self, username: str, query: str) -> dict:
        from tools.knowledge_graph import run
        return run(action="query", query=query, username=username)

    def path(self, username: str, source: str, target: str) -> dict:
        from tools.knowledge_graph import run
        return run(action="shortest_path", source=source, target=target, username=username)

    def stats(self, username: str) -> dict:
        from tools.knowledge_graph import run
        return run(action="stats", username=username)


# ── Tier 4: Vector Memory ─────────────────────────────────────────────────────
class VectorMemory:
    """
    Semantic similarity memory. Wraps the existing vector_memory.py module.
    """

    def store(self, username: str, user_msg: str, ai_reply: str, chat_id: str = "") -> None:
        try:
            import vector_memory as vm
            vm.store_conversation(username, user_msg, ai_reply, chat_id)
        except Exception as e:
            log.debug("VectorMemory.store: %s", e)

    def retrieve(self, username: str, query: str, n: int = 3) -> list[str]:
        try:
            import vector_memory as vm
            return vm.retrieve_relevant(username, query, n=n)
        except Exception as e:
            log.debug("VectorMemory.retrieve: %s", e)
            return []

    def search_memories(self, username: str, query: str, n: int = 5) -> list[str]:
        return self.retrieve(username, query, n)


# ── Tier 5: Archive Memory ────────────────────────────────────────────────────
class ArchiveMemory:
    """
    Cold long-term storage. Conversations and facts kept indefinitely.
    Searchable by keyword but not loaded into active context automatically.
    """

    def _ensure(self) -> None:
        with _conn() as con:
            con.executescript("""
            CREATE TABLE IF NOT EXISTS memory_archive (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                username   TEXT NOT NULL,
                chat_id    TEXT DEFAULT '',
                role       TEXT DEFAULT '',
                content    TEXT NOT NULL,
                source     TEXT DEFAULT 'conversation',
                archived_at INTEGER DEFAULT (strftime('%s','now'))
            );
            CREATE INDEX IF NOT EXISTS idx_ma_user ON memory_archive(username);
            CREATE VIRTUAL TABLE IF NOT EXISTS memory_archive_fts
                USING fts5(content, username, tokenize='porter ascii');
            """)

    def store(self, username: str, content: str, source: str = "manual",
              chat_id: str = "", role: str = "") -> None:
        self._ensure()
        with _conn() as con:
            con.execute(
                "INSERT INTO memory_archive(username,chat_id,role,content,source) VALUES(?,?,?,?,?)",
                (username, chat_id, role, content[:8000], source),
            )
            try:
                con.execute(
                    "INSERT INTO memory_archive_fts(content,username) VALUES(?,?)",
                    (content[:8000], username),
                )
            except Exception:
                pass  # FTS not always available

    def bulk_store(self, username: str, rows: list[dict]) -> None:
        self._ensure()
        with _conn() as con:
            for row in rows:
                con.execute(
                    "INSERT INTO memory_archive(username,chat_id,role,content,source) VALUES(?,?,?,?,?)",
                    (username, row.get("chat_id",""), row.get("role",""),
                     row.get("content","")[:8000], "auto_archive"),
                )

    def search(self, username: str, query: str, limit: int = 10) -> list[dict]:
        self._ensure()
        q = f"%{query}%"
        with _conn() as con:
            rows = con.execute(
                "SELECT content,source,archived_at FROM memory_archive "
                "WHERE username=? AND content LIKE ? ORDER BY archived_at DESC LIMIT ?",
                (username, q, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def stats(self, username: str) -> dict:
        self._ensure()
        with _conn() as con:
            total = con.execute(
                "SELECT COUNT(*) FROM memory_archive WHERE username=?", (username,)
            ).fetchone()[0]
        return {"archived_items": total}


# ── Unified facade ─────────────────────────────────────────────────────────────
class MemorySystem:
    """
    Single entry point for all 5 memory tiers.

        from services.memory_layers import mem

        mem.working.set(...)
        mem.conversation.append(...)
        mem.knowledge.add_relation(...)
        mem.vector.store(...)
        mem.archive.store(...)
    """

    def __init__(self) -> None:
        self.working      = WorkingMemory()
        self.conversation = ConversationMemory()
        self.knowledge    = KnowledgeGraphMemory()
        self.vector       = VectorMemory()
        self.archive      = ArchiveMemory()

    def recall(self, username: str, query: str, chat_id: str = "") -> dict:
        """
        Multi-tier recall: returns the most relevant memory from all tiers.
        Useful for injecting context into an agent before it responds.
        """
        results: dict[str, Any] = {}

        # Tier 1 — working memory keys (no semantic search)
        results["working_keys"] = self.working.keys()

        # Tier 4 — vector semantic search (best for NL queries)
        vec = self.vector.retrieve(username, query, n=3)
        if vec:
            results["semantic"] = vec

        # Tier 3 — knowledge graph
        kg = self.knowledge.query(username, query)
        if kg.get("result") and "No matches" not in kg["result"]:
            results["knowledge"] = kg["result"]

        # Tier 5 — archive keyword search
        arch = self.archive.search(username, query, limit=3)
        if arch:
            results["archive"] = [a["content"][:300] for a in arch]

        return results

    def context_string(self, username: str, query: str) -> str:
        """Return a formatted multi-tier memory string for system prompt injection."""
        r = self.recall(username, query)
        parts = []
        if r.get("semantic"):
            parts.append("Relevant past conversations:\n" + "\n---\n".join(r["semantic"][:2]))
        if r.get("knowledge"):
            parts.append("Knowledge graph:\n" + r["knowledge"])
        if r.get("archive"):
            parts.append("Archived insights:\n" + "\n".join(r["archive"][:2]))
        return "\n\n".join(parts)


# ── Singleton ─────────────────────────────────────────────────────────────────
mem = MemorySystem()
