"""
vector_memory.py — Semantic memory for Assist Neo
===================================================
Uses ChromaDB (real vector embeddings) when installed.
Falls back to SQLite FTS5 (full-text search) automatically — no setup needed.

Install for best results:
    pip install chromadb
"""

import os
import sqlite3
import time
import hashlib
import logging

log = logging.getLogger("vector_memory")

BASE     = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE, "assistneo.db")
CHROMA_DIR = os.path.join(BASE, "chroma_db")

# ── Try importing ChromaDB ────────────────────────────────────────────────────
try:
    import chromadb
    _CHROMA_OK = True
    log.info("vector_memory: ChromaDB backend active")
except ImportError:
    _CHROMA_OK = False
    log.info("vector_memory: ChromaDB not found — using SQLite FTS5 fallback")

# ── SQLite FTS5 fallback ─────────────────────────────────────────────────────

def _fts_init():
    """Create the FTS5 conversation memory table if it doesn't exist."""
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("""
        CREATE TABLE IF NOT EXISTS conv_memory (
            id        TEXT PRIMARY KEY,
            username  TEXT NOT NULL,
            query     TEXT NOT NULL,
            reply     TEXT NOT NULL,
            chat_id   TEXT DEFAULT '',
            ts        REAL DEFAULT 0
        )
    """)
    # FTS5 virtual table over conv_memory
    con.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS conv_memory_fts
        USING fts5(id UNINDEXED, username UNINDEXED, content, content='conv_memory', content_rowid='rowid')
    """)
    # Triggers to keep FTS in sync
    con.execute("""
        CREATE TRIGGER IF NOT EXISTS conv_memory_ai AFTER INSERT ON conv_memory BEGIN
            INSERT INTO conv_memory_fts(rowid, id, username, content)
            VALUES (new.rowid, new.id, new.username, new.query || ' ' || new.reply);
        END
    """)
    con.execute("""
        CREATE TRIGGER IF NOT EXISTS conv_memory_ad AFTER DELETE ON conv_memory BEGIN
            INSERT INTO conv_memory_fts(conv_memory_fts, rowid, id, username, content)
            VALUES ('delete', old.rowid, old.id, old.username, old.query || ' ' || old.reply);
        END
    """)
    con.commit()
    con.close()

def _fts_store(username: str, query: str, reply: str, chat_id: str = ""):
    doc_id = hashlib.md5(f"{username}:{time.time()}:{query[:50]}".encode()).hexdigest()
    con = sqlite3.connect(DB_PATH)
    try:
        con.execute(
            "INSERT OR IGNORE INTO conv_memory (id, username, query, reply, chat_id, ts) VALUES (?,?,?,?,?,?)",
            (doc_id, username, query[:800], reply[:800], chat_id, time.time())
        )
        con.commit()
    finally:
        con.close()

def _fts_retrieve(username: str, query: str, n: int = 4) -> list:
    """Full-text search for relevant past conversations."""
    # Escape FTS special chars
    safe_query = " OR ".join(
        f'"{w}"' for w in query.split()[:8] if len(w) > 2
    )
    if not safe_query:
        return []
    con = sqlite3.connect(DB_PATH)
    try:
        rows = con.execute("""
            SELECT cm.query, cm.reply
            FROM conv_memory cm
            JOIN conv_memory_fts fts ON cm.rowid = fts.rowid
            WHERE fts.content MATCH ? AND cm.username = ?
            ORDER BY rank
            LIMIT ?
        """, (safe_query, username, n)).fetchall()
        return [f"Q: {r[0]}\nA: {r[1]}" for r in rows]
    except Exception as e:
        log.warning("FTS search failed: %s", e)
        return []
    finally:
        con.close()

def _fts_clear(username: str):
    con = sqlite3.connect(DB_PATH)
    try:
        con.execute("DELETE FROM conv_memory WHERE username = ?", (username,))
        con.commit()
    finally:
        con.close()

# ── ChromaDB backend ─────────────────────────────────────────────────────────

_chroma_client = None
_chroma_cols   = {}

def _get_chroma_client():
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
    return _chroma_client

def _get_col(username: str):
    if username not in _chroma_cols:
        client = _get_chroma_client()
        _chroma_cols[username] = client.get_or_create_collection(
            name=f"mem_{username}",
            metadata={"hnsw:space": "cosine"}
        )
    return _chroma_cols[username]

def _chroma_store(username: str, query: str, reply: str, chat_id: str = ""):
    doc_id  = hashlib.md5(f"{username}:{time.time()}:{query[:50]}".encode()).hexdigest()
    content = f"Q: {query[:600]}\nA: {reply[:600]}"
    col = _get_col(username)
    col.add(
        documents=[content],
        metadatas=[{"username": username, "chat_id": chat_id, "ts": str(time.time())}],
        ids=[doc_id]
    )

def _chroma_retrieve(username: str, query: str, n: int = 4) -> list:
    try:
        col  = _get_col(username)
        cnt  = col.count()
        if cnt == 0:
            return []
        res = col.query(query_texts=[query], n_results=min(n, cnt))
        return res["documents"][0] if res["documents"] else []
    except Exception as e:
        log.warning("ChromaDB retrieve failed: %s", e)
        return []

def _chroma_clear(username: str):
    try:
        _get_chroma_client().delete_collection(f"mem_{username}")
        _chroma_cols.pop(username, None)
    except Exception as e:
        log.warning("ChromaDB clear failed: %s", e)

# ── Public API ────────────────────────────────────────────────────────────────

def init():
    """Call once at app startup."""
    if not _CHROMA_OK:
        _fts_init()

def store_conversation(username: str, query: str, reply: str, chat_id: str = ""):
    """Persist a Q&A pair to the vector/FTS memory store."""
    try:
        if _CHROMA_OK:
            _chroma_store(username, query, reply, chat_id)
        else:
            _fts_store(username, query, reply, chat_id)
    except Exception as e:
        log.error("store_conversation failed: %s", e)

def retrieve_relevant(username: str, query: str, n: int = 4) -> list:
    """
    Return up to n past Q&A strings most relevant to the current query.
    Each item is formatted as 'Q: ...\nA: ...'
    """
    try:
        if _CHROMA_OK:
            return _chroma_retrieve(username, query, n)
        else:
            return _fts_retrieve(username, query, n)
    except Exception as e:
        log.error("retrieve_relevant failed: %s", e)
        return []

def clear_user_memory(username: str):
    """Wipe all stored conversation memory for a user."""
    try:
        if _CHROMA_OK:
            _chroma_clear(username)
        else:
            _fts_clear(username)
    except Exception as e:
        log.error("clear_user_memory failed: %s", e)

def memory_count(username: str) -> int:
    """Return how many conversation pairs are stored for a user."""
    try:
        if _CHROMA_OK:
            return _get_col(username).count()
        else:
            con = sqlite3.connect(DB_PATH)
            n = con.execute("SELECT COUNT(*) FROM conv_memory WHERE username=?", (username,)).fetchone()[0]
            con.close()
            return n
    except Exception:
        return 0
