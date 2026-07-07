"""
services/semantic_cache.py -- near-duplicate questions answered from cache.

Every Q&A pair is embedded (ChromaDB); a repeat question within the
similarity threshold returns instantly with zero tokens. Falls back to an
exact-match SQLite cache when ChromaDB is unavailable. Set SEMANTIC_CACHE=0
to disable. TTL 24h so answers never go stale.
"""
import hashlib
import os
import sqlite3
import time
import logging

log = logging.getLogger("services.semantic_cache")

BASE    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE, "aiaurum.db")
TTL_S   = 24 * 3600
THRESHOLD = float(os.getenv("CACHE_THRESHOLD", "0.08"))  # cosine distance

_col = None


def _enabled() -> bool:
    return os.getenv("SEMANTIC_CACHE", "1") == "1"


def _collection():
    global _col
    if _col is not None:
        return _col
    import chromadb
    client = chromadb.PersistentClient(path=os.path.join(BASE, "chroma_db"))
    _col = client.get_or_create_collection("qa_cache",
                                           metadata={"hnsw:space": "cosine"})
    return _col


def _sql():
    con = sqlite3.connect(DB_PATH, timeout=5)
    con.execute("""CREATE TABLE IF NOT EXISTS qa_cache (
        qhash TEXT PRIMARY KEY, username TEXT, question TEXT, answer TEXT,
        created_at INTEGER)""")
    return con


def lookup(username: str, question: str):
    """Return a cached answer or None."""
    if not _enabled() or len(question) < 8:
        return None
    q = question.strip()
    try:
        col = _collection()
        res = col.query(query_texts=[q], n_results=1,
                        where={"username": username},
                        include=["documents", "metadatas", "distances"])
        docs  = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        if docs and dists and dists[0] <= THRESHOLD:
            if time.time() - (metas[0] or {}).get("ts", 0) <= TTL_S:
                log.info("semantic cache HIT (distance %.3f)", dists[0])
                return docs[0]
        return None
    except Exception:
        pass
    try:  # exact-match fallback
        h = hashlib.sha1((username + "|" + q.lower()).encode()).hexdigest()
        con = _sql()
        row = con.execute("SELECT answer, created_at FROM qa_cache WHERE qhash=?",
                          (h,)).fetchone()
        con.close()
        if row and time.time() - row[1] <= TTL_S:
            log.info("exact cache HIT")
            return row[0]
    except Exception as e:
        log.debug("cache lookup: %s", e)
    return None


def store(username: str, question: str, answer: str):
    if not _enabled() or len(question) < 8 or not answer or len(answer) < 20:
        return
    if answer.startswith(("[AI error", "[error", "[Error")):
        return
    q = question.strip()
    try:
        col = _collection()
        h = hashlib.sha1((username + "|" + q.lower()).encode()).hexdigest()
        col.upsert(ids=[h], documents=[answer[:6000]],
                   metadatas=[{"username": username, "ts": int(time.time()),
                               "q": q[:200]}])
        return
    except Exception:
        pass
    try:
        h = hashlib.sha1((username + "|" + q.lower()).encode()).hexdigest()
        con = _sql()
        con.execute("INSERT OR REPLACE INTO qa_cache VALUES (?,?,?,?,?)",
                    (h, username, q[:400], answer[:6000], int(time.time())))
        con.commit(); con.close()
    except Exception as e:
        log.debug("cache store: %s", e)
