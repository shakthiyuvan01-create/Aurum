"""
services/learning.py -- personal knowledge base (Jarvis-style Learning System).

Drop .txt files in learning_data/ with personal info, preferences, context.
They are chunked, embedded (ChromaDB), and the most relevant chunks are
retrieved per question and injected into the system prompt. Token usage stays
bounded no matter how much you add -- only the top matches are sent.

Also stores facts added at runtime via /learning/add. Shared across sessions.
"""
import os
import hashlib
import logging
import threading

log = logging.getLogger("services.learning")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEARN_DIR = os.path.join(BASE, "learning_data")
_indexed_files = {}
_lock = threading.Lock()


def _chunks(text, size=800, overlap=100):
    text = text.strip()
    if len(text) <= size:
        return [text] if text else []
    out, i = [], 0
    while i < len(text):
        end = min(i + size, len(text))
        if end < len(text):
            brk = text.rfind("\n", i + size // 2, end)
            if brk == -1:
                brk = text.rfind(". ", i + size // 2, end)
            if brk != -1:
                end = brk + 1
        out.append(text[i:end].strip())
        i = max(end - overlap, i + 1)
    return [c for c in out if c]


import sqlite3
_DB = os.path.join(BASE, "aiaurum.db")


def _sql():
    con = sqlite3.connect(_DB, timeout=10)
    con.execute("""CREATE TABLE IF NOT EXISTS learning_facts (
        id TEXT PRIMARY KEY, username TEXT, source TEXT, text TEXT)""")
    return con


def _chroma_ok():
    try:
        import chromadb  # noqa
        return True
    except Exception:
        return False


def _col(username="global"):
    import chromadb
    client = chromadb.PersistentClient(path=os.path.join(BASE, "chroma_db"))
    safe = "".join(c for c in username if c.isalnum()) or "global"
    return client.get_or_create_collection("learning_" + safe,
                                            metadata={"hnsw:space": "cosine"})


def index_file(path, username="global"):
    try:
        st = os.stat(path)
        sig = "%s:%d:%d" % (path, st.st_size, int(st.st_mtime))
        if _indexed_files.get(path) == sig:
            return 0
        text = open(path, encoding="utf-8", errors="ignore").read()
        if len(text) < 20:
            return 0
        chunks = _chunks(text)
        if not chunks:
            return 0
        fid = hashlib.sha1(path.encode()).hexdigest()[:10]
        fname = os.path.basename(path)
        if _chroma_ok():
            col = _col(username)
            col.upsert(ids=["%s_%d" % (fid, i) for i in range(len(chunks))],
                       documents=chunks,
                       metadatas=[{"file": fname} for _ in chunks])
        with _sql() as con:
            con.executemany(
                "INSERT OR REPLACE INTO learning_facts (id, username, source, text) VALUES (?,?,?,?)",
                [("%s_%d" % (fid, i), username, fname, chunks[i]) for i in range(len(chunks))])
        _indexed_files[path] = sig
        log.info("learning: indexed %s (%d chunks)", os.path.basename(path), len(chunks))
        return len(chunks)
    except Exception as e:
        log.debug("index_file %s: %s", path, e)
        return 0


def add_fact(text, username="global"):
    """Store a fact typed at runtime (chroma if available + sqlite always)."""
    import time
    fid = "fact_%d" % int(time.time() * 1000)
    text = text[:2000]
    try:
        if _chroma_ok():
            _col(username).upsert(ids=[fid], documents=[text],
                                  metadatas=[{"file": "runtime"}])
        with _sql() as con:
            con.execute("INSERT OR REPLACE INTO learning_facts (id, username, source, text) "
                        "VALUES (?,?,?,?)", (fid, username, "runtime", text))
        return {"ok": True}
    except Exception as e:
        return {"error": str(e)}


def reindex_all(username="global"):
    """Index every .txt in learning_data/."""
    os.makedirs(LEARN_DIR, exist_ok=True)
    total = 0
    for f in os.listdir(LEARN_DIR):
        if f.lower().endswith(".txt") and f != "README.txt":
            total += index_file(os.path.join(LEARN_DIR, f), username)
    return total


def retrieve(query, username="global", top_k=4):
    """Most relevant learning chunks (semantic via chroma, else keyword sqlite)."""
    if _chroma_ok():
        try:
            res = _col(username).query(query_texts=[query], n_results=top_k,
                                       include=["documents"])
            hits = (res.get("documents") or [[]])[0]
            if hits:
                return hits
        except Exception as e:
            log.debug("chroma retrieve: %s", e)
    # sqlite keyword fallback
    try:
        words = [w.lower() for w in query.split() if len(w) > 3][:6]
        with _sql() as con:
            if words:
                clause = " OR ".join("lower(text) LIKE ?" for _ in words)
                rows = con.execute(
                    "SELECT text FROM learning_facts WHERE (%s) LIMIT ?" % clause,
                    ["%%%s%%" % w for w in words] + [top_k]).fetchall()
            else:
                rows = con.execute("SELECT text FROM learning_facts LIMIT ?",
                                   (top_k,)).fetchall()
        return [r[0] for r in rows]
    except Exception as e:
        log.debug("sqlite retrieve: %s", e)
        return []


def context(query, username="global") -> str:
    """Formatted block for the system prompt."""
    hits = retrieve(query, username)
    if not hits:
        return ""
    return "\n\n=== WHAT I'VE LEARNED ABOUT YOU ===\n" + "\n".join("- " + h for h in hits)


def stats(username="global"):
    files = []
    try:
        files = [f for f in os.listdir(LEARN_DIR)
                 if f.endswith(".txt") and f != "README.txt"]
    except OSError:
        pass
    n = 0
    try:
        with _sql() as con:
            n = con.execute("SELECT COUNT(*) FROM learning_facts").fetchone()[0]
    except Exception:
        pass
    return {"chunks": n, "files": files,
            "backend": "chroma+sqlite" if _chroma_ok() else "sqlite"}


def supervisor():
    """Scheduler hook: pick up new/changed learning files."""
    try:
        reindex_all()
    except Exception as e:
        log.debug("learning supervisor: %s", e)
