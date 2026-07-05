"""
services/rag_service.py -- document RAG pipeline.

    PDF/DOCX text -> chunk -> embed -> ChromaDB -> retrieve top-k -> LLM

Used by tools/document_agent.py for Q&A on large documents so we send only
the relevant chunks to the model instead of huge prompts.
Falls back gracefully (returns []) when ChromaDB is unavailable.
"""
import hashlib
import logging
import os
import threading

log = logging.getLogger("services.rag")

BASE       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROMA_DIR = os.path.join(BASE, "chroma_db")

_client   = None
_lock     = threading.Lock()
_indexed: set = set()   # doc fingerprints already embedded this process


def _col(username: str):
    global _client
    import chromadb
    with _lock:
        if _client is None:
            _client = chromadb.PersistentClient(path=CHROMA_DIR)
    safe = "".join(c for c in (username or "default") if c.isalnum()) or "default"
    return _client.get_or_create_collection("docs_" + safe,
                                            metadata={"hnsw:space": "cosine"})


def chunk_text(text: str, size: int = 1200, overlap: int = 150) -> list:
    """Split text into overlapping chunks on paragraph boundaries when possible."""
    text = text.strip()
    if len(text) <= size:
        return [text] if text else []
    chunks, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            brk = text.rfind("\n", start + size // 2, end)
            if brk == -1:
                brk = text.rfind(". ", start + size // 2, end)
            if brk != -1:
                end = brk + 1
        chunks.append(text[start:end].strip())
        start = max(end - overlap, start + 1)
    return [c for c in chunks if c]


def doc_fingerprint(file_path: str, text: str = "") -> str:
    try:
        st = os.stat(file_path)
        raw = "%s|%d|%d" % (file_path, st.st_size, int(st.st_mtime))
    except OSError:
        raw = file_path + "|" + str(len(text))
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def index_document(file_path: str, text: str, username: str = "default") -> str:
    """Chunk + embed a document. Idempotent per file version. Returns doc_id."""
    doc_id = doc_fingerprint(file_path, text)
    key = username + ":" + doc_id
    if key in _indexed:
        return doc_id
    try:
        col = _col(username)
        existing = col.get(where={"doc_id": doc_id}, limit=1)
        if existing and existing.get("ids"):
            _indexed.add(key)
            return doc_id
        chunks = chunk_text(text)
        if not chunks:
            return doc_id
        col.add(
            ids=["%s_%d" % (doc_id, i) for i in range(len(chunks))],
            documents=chunks,
            metadatas=[{"doc_id": doc_id, "chunk": i,
                        "file": os.path.basename(file_path)} for i in range(len(chunks))],
        )
        _indexed.add(key)
        log.info("rag: indexed %s (%d chunks) for %s",
                 os.path.basename(file_path), len(chunks), username)
    except Exception as e:
        log.warning("rag index failed: %s", e)
    return doc_id


def retrieve(query: str, username: str = "default", doc_id: str = None,
             top_k: int = 5) -> list:
    """Return the top-k most relevant chunks (list of strings)."""
    try:
        col = _col(username)
        kwargs = {"query_texts": [query], "n_results": top_k}
        if doc_id:
            kwargs["where"] = {"doc_id": doc_id}
        res = col.query(**kwargs)
        return (res.get("documents") or [[]])[0]
    except Exception as e:
        log.warning("rag retrieve failed: %s", e)
        return []


def qa_context(file_path: str, text: str, question: str,
               username: str = "default", top_k: int = 5) -> str:
    """One-call helper: index (if needed) + retrieve. Returns joined context
    with source citations, falling back to the head of the document."""
    doc_id = index_document(file_path, text, username)
    chunks = retrieve_with_meta(question, username, doc_id=doc_id, top_k=top_k)
    if chunks:
        return "\n\n---\n\n".join(
            "[Source: %s, part %s]\n%s" % (c["file"], c["chunk"], c["text"])
            for c in chunks)
    return text[:6000]


def retrieve_with_meta(query: str, username: str = "default", doc_id: str = None,
                       top_k: int = 5) -> list:
    """Top-k chunks with their source metadata for citations."""
    try:
        col = _col(username)
        kwargs = {"query_texts": [query], "n_results": top_k,
                  "include": ["documents", "metadatas"]}
        if doc_id:
            kwargs["where"] = {"doc_id": doc_id}
        res = col.query(**kwargs)
        docs  = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        return [{"text": d, "file": (m or {}).get("file", "?"),
                 "chunk": (m or {}).get("chunk", "?")}
                for d, m in zip(docs, metas)]
    except Exception as e:
        log.warning("rag retrieve failed: %s", e)
        return []
