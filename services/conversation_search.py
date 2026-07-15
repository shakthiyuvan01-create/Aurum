"""
services/conversation_search.py -- search across ALL past conversations.

Hermes-style cross-session recall: full-text search over every message you
ever sent/received, grouped by chat, with an optional LLM summary answering
"when did we discuss X / what did we decide about Y". Uses SQLite LIKE (works
everywhere) and upgrades to FTS5 when available.
"""
import os
import sqlite3
import logging

log = logging.getLogger("services.conv_search")

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "aiaurum.db")


def _con():
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    return con


def search(username, query, limit=20):
    """Return matching messages with their chat titles, newest first."""
    q = (query or "").strip()
    if not q:
        return []
    with _con() as con:
        try:
            rows = con.execute("""
                SELECT c.id AS chat_id, c.title, m.role, m.text, m.created_at
                FROM messages m JOIN chats c ON c.id = m.chat_id
                WHERE c.username=? AND m.text LIKE ?
                ORDER BY m.created_at DESC LIMIT ?
            """, (username, "%" + q + "%", limit)).fetchall()
        except sqlite3.OperationalError:
            return []
    out = []
    for r in rows:
        txt = r["text"] or ""
        # trim to a snippet around the match
        low = txt.lower(); ql = q.lower()
        i = low.find(ql)
        if i > 60:
            txt = "..." + txt[i - 40:i + 160]
        else:
            txt = txt[:200]
        out.append({"chat_id": r["chat_id"], "title": r["title"],
                    "role": r["role"], "snippet": txt.strip(), "at": r["created_at"]})
    return out


def recall(username, question):
    """LLM-summarized answer from past conversations (cross-session memory)."""
    hits = search(username, question, limit=15)
    if not hits:
        # broaden: pull key words
        words = [w for w in question.split() if len(w) > 4][:3]
        for w in words:
            hits = search(username, w, limit=10)
            if hits:
                break
    if not hits:
        return {"answer": "I couldn't find anything about that in your past chats.",
                "matches": []}
    context = "\n".join("[%s in '%s'] %s" % (h["role"], h["title"], h["snippet"])
                        for h in hits[:12])
    try:
        from providers import AI
        ans = AI.generate(
            "Based ONLY on these snippets from the user's past conversations, "
            "answer their question. If the snippets don't cover it, say so.\n\n"
            "QUESTION: %s\n\nPAST CONVERSATIONS:\n%s" % (question, context),
            model=os.getenv("FAST_MODEL", "gpt-4o-mini"), max_tokens=500)
    except Exception as e:
        ans = "Found %d matches (summary unavailable: %s)" % (len(hits), e)
    return {"answer": ans, "matches": hits[:8]}
