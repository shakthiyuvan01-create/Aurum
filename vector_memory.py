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

# ── Retrieval tuning ─────────────────────────────────────────────────────────
SIMILARITY_THRESHOLD = 0.30   # ChromaDB distance: 0 = identical, 2 = opposite (cosine)
RECENCY_HALF_LIFE    = 7 * 24 * 3600   # 7 days — older memories get lower recency boost
IMPORTANCE_KEYWORDS  = {
    "remember", "important", "always", "never", "prefer", "hate", "love",
    "name", "birthday", "address", "work", "goal", "project", "deadline",
}

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
    """Full-text search with recency+importance re-ranking."""
    safe_query = " OR ".join(
        f'"{w}"' for w in query.split()[:8] if len(w) > 2
    )
    if not safe_query:
        return []
    con = sqlite3.connect(DB_PATH)
    try:
        # Fetch extra candidates for re-ranking
        rows = con.execute("""
            SELECT cm.query, cm.reply, cm.ts
            FROM conv_memory cm
            JOIN conv_memory_fts fts ON cm.rowid = fts.rowid
            WHERE fts.content MATCH ? AND cm.username = ?
            ORDER BY rank
            LIMIT ?
        """, (safe_query, username, n * 3)).fetchall()
        if not rows:
            return []
        # Re-rank by importance + recency (FTS has no distance, use rank order)
        scored = []
        for i, (q, a, ts) in enumerate(rows):
            doc       = f"Q: {q}\nA: {a}"
            recency   = _recency_score(float(ts or 0))
            importance = _importance_score(doc)
            fts_score = 1.0 - (i / max(len(rows), 1)) * 0.5  # FTS rank → 0.5–1.0
            score     = fts_score * 0.5 + recency * 0.3 + importance * 0.2
            scored.append((score, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in scored[:n]]
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



# ── Retrieval scoring helpers ─────────────────────────────────────────────────

def _recency_score(ts: float) -> float:
    """Returns 0–1; 1 = just stored, decays with RECENCY_HALF_LIFE."""
    if not ts:
        return 0.5
    age = time.time() - float(ts)
    return max(0.0, 1.0 - age / (RECENCY_HALF_LIFE * 2))


def _importance_score(text: str) -> float:
    """Returns 0–1 based on length and presence of important keywords."""
    base  = min(1.0, len(text) / 400)          # longer = more informative
    kw    = sum(1 for k in IMPORTANCE_KEYWORDS if k in text.lower())
    boost = min(0.5, kw * 0.1)
    return min(1.0, base + boost)


def _rank_results(docs: list[str], distances: list[float],
                  timestamps: list[float]) -> list[str]:
    """
    Re-rank retrieved memories by a combined score:
        score = (1 - norm_distance) * 0.5 + recency * 0.3 + importance * 0.2
    Filter out anything below SIMILARITY_THRESHOLD.
    """
    scored = []
    for doc, dist, ts in zip(docs, distances, timestamps):
        if dist > (2 - SIMILARITY_THRESHOLD * 2):   # cosine: filter far results
            continue
        sim       = max(0.0, 1.0 - dist / 2.0)
        recency   = _recency_score(ts)
        importance = _importance_score(doc)
        score     = sim * 0.5 + recency * 0.3 + importance * 0.2
        scored.append((score, doc))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in scored]

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
        metadatas=[{"username": username, "chat_id": chat_id, "ts": time.time()}],
        ids=[doc_id]
    )

def _chroma_retrieve(username: str, query: str, n: int = 4) -> list:
    try:
        col = _get_col(username)
        cnt = col.count()
        if cnt == 0:
            return []
        # Fetch extra candidates so we can re-rank and filter
        fetch_n = min(cnt, max(n * 3, 12))
        res = col.query(
            query_texts=[query],
            n_results=fetch_n,
            include=["documents", "distances", "metadatas"],
        )
        if not res["documents"] or not res["documents"][0]:
            return []
        docs      = res["documents"][0]
        distances = res["distances"][0]
        timestamps = [float(m.get("ts", 0)) for m in res["metadatas"][0]]
        ranked = _rank_results(docs, distances, timestamps)
        log.debug("chroma_retrieve: user=%s candidates=%d ranked=%d returned=%d",
                  username, len(docs), len(ranked), min(n, len(ranked)))
        return ranked[:n]
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
    except Exception as _e:
        log.debug("memory_count failed: %s", _e)
        return 0
