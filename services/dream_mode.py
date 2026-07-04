"""
services/dream_mode.py -- idle-time "dreaming".

Nightly (02:30) the AI reviews what the user worked on recently, then:
  - researches their frequent topics for fresh ideas
  - looks for recurring errors worth fixing
  - writes a "Dream Report" into the Document Canvas + memory

Gated behind the self_improve permission. Suggestions only, never acts.
"""
import os
import sqlite3
import time
import logging

log = logging.getLogger("services.dream_mode")

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "aiaurum.db")


def run_dream() -> dict:
    from services.permission_manager import perms
    if not perms.check("self_improve"):
        return {"skipped": True, "reason": "self_improve permission disabled"}

    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    try:
        users = [r["username"] for r in
                 con.execute("SELECT username FROM users LIMIT 10").fetchall()]
        reports = {}
        for uname in users:
            titles = [r["title"] for r in con.execute(
                "SELECT title FROM chats WHERE username=? ORDER BY created_at DESC LIMIT 30",
                (uname,)).fetchall()]
            hist = [r["title"] for r in con.execute(
                "SELECT title FROM task_history WHERE username=? "
                "ORDER BY created_at DESC LIMIT 20", (uname,)).fetchall()]
            if not titles and not hist:
                continue
            discoveries = ""
            try:
                import tools as _tools
                top = titles[0] if titles else "AI tools"
                r = _tools.call("web_search",
                                query="new tools libraries research " + str(top)[:60])
                discoveries = str(r.get("result") or r.get("message") or "")[:1500]
            except Exception:
                pass
            from providers import AI
            report = AI.generate(
                "You are the user's AI reviewing their recent activity while they "
                "sleep. Based on their recent chat topics and tasks, write a short "
                "'Dream Report': 3 fresh ideas worth exploring, 2 things that look "
                "worth automating or fixing, and 1 learning suggestion. Be specific "
                "to their interests.\n\nRECENT CHATS: %s\n\nRECENT TASKS: %s"
                % ("; ".join(titles[:30]), "; ".join(hist[:20]))
                + ("\n\nFRESH WEB FINDINGS TO MINE FOR DISCOVERIES:\n" + discoveries
                   if discoveries else ""),
                model="gpt-4o-mini", max_tokens=600, temperature=0.5)
            if report.startswith("[AI error"):
                continue
            stamp = time.strftime("%Y-%m-%d")
            con.execute(
                "INSERT INTO canvas_docs (username, title, content) VALUES (?,?,?)",
                (uname, "Dream Report " + stamp, report))
            try:
                import db as _db
                _db.add_memory(uname, "Dream report %s: %s" % (stamp, report[:300]))
            except Exception:
                pass
            reports[uname] = len(report)
        con.commit()
        log.info("dream mode: wrote %d reports", len(reports))
        return {"ok": True, "reports": reports}
    finally:
        con.close()
