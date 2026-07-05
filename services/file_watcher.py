"""
services/file_watcher.py -- auto-index new files into RAG.

Watches WATCH_DIR (default: workspace/inbox). Drop a .txt/.md/.csv/.pdf/.docx
in there and it gets indexed into the vector store automatically -- then just
ask questions about it in chat. Polling-based (no extra dependency).
"""
import os
import time
import threading
import logging

log = logging.getLogger("services.file_watcher")

_seen: dict = {}
_started = False
EXT = (".txt", ".md", ".csv", ".log", ".py", ".pdf", ".docx")


def _extract(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext in (".txt", ".md", ".csv", ".log", ".py"):
            return open(path, encoding="utf-8", errors="ignore").read()
        from tools.document_agent import _extract_text
        return _extract_text(path)
    except Exception as e:
        log.warning("extract failed for %s: %s", path, e)
        return ""


def _scan(watch_dir: str, username: str):
    for f in os.listdir(watch_dir):
        p = os.path.join(watch_dir, f)
        if not os.path.isfile(p) or not f.lower().endswith(EXT):
            continue
        try:
            mtime = os.path.getmtime(p)
        except OSError:
            continue
        if _seen.get(p) == mtime:
            continue
        _seen[p] = mtime
        text = _extract(p)
        if len(text) < 40:
            continue
        try:
            from services.rag_service import index_document
            index_document(p, text, username)
            import db as _db
            _db.add_memory(username, "Indexed document: %s (%d chars)" % (f, len(text)))
            log.info("file watcher indexed: %s", f)
        except Exception as e:
            log.warning("index failed for %s: %s", f, e)


def _loop():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    watch_dir = os.getenv("WATCH_DIR", os.path.join(base, "workspace", "inbox"))
    username = os.getenv("WATCH_USER", "default")
    os.makedirs(watch_dir, exist_ok=True)
    log.info("file watcher: %s (drop files here to auto-index)", watch_dir)
    while True:
        try:
            _scan(watch_dir, username)
        except Exception as e:
            log.debug("watch scan: %s", e)
        time.sleep(20)


def start():
    global _started
    if _started or os.getenv("DISABLE_FILE_WATCHER") == "1":
        return False
    _started = True
    threading.Thread(target=_loop, daemon=True).start()
    return True
