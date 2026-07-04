"""
services/experience_db.py -- every solved problem becomes reusable experience.

After each team run: problem -> solution -> lesson -> reusable strategy,
stored and retrievable. relevant_experience() is injected into future team
runs so the AI genuinely gains experience.
"""
import os
import sqlite3
import logging

log = logging.getLogger("services.experience")

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "aiaurum.db")


def _conn():
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("""CREATE TABLE IF NOT EXISTS experiences (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username   TEXT NOT NULL,
        problem    TEXT NOT NULL,
        strategy   TEXT NOT NULL,
        lesson     TEXT DEFAULT '',
        uses       INTEGER DEFAULT 0,
        created_at INTEGER DEFAULT (strftime('%s','now')))""")
    return con


def learn_from_run(username: str, goal: str, agent_outputs: list, reply: str) -> None:
    """Background: distill a team run into a reusable strategy."""
    try:
        from services.permission_manager import perms
        if not perms.check("background_ai"):
            return
        from providers import AI
        raw = AI.generate(
            "A multi-agent run just solved this. Distill it into experience. "
            'Reply ONLY JSON: {"strategy": "reusable 1-2 sentence approach", '
            '"lesson": "1 sentence lesson"}. If nothing generalizable, reply '
            '{"strategy": ""}.\n\nPROBLEM: %s\n\nAPPROACH: %s'
            % (goal[:300], "; ".join("%s did %s" % (o["agent"], o["task"][:80])
                                     for o in agent_outputs[:6])),
            model="gpt-4o-mini", max_tokens=120, temperature=0.2)
        import json, re
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            return
        d = json.loads(m.group(0))
        if d.get("strategy"):
            with _conn() as con:
                con.execute(
                    "INSERT INTO experiences (username, problem, strategy, lesson) "
                    "VALUES (?,?,?,?)",
                    (username, goal[:300], d["strategy"][:500], d.get("lesson", "")[:300]))
            log.info("experience stored for %s", username)
    except Exception as e:
        log.debug("experience learn failed: %s", e)


def relevant_experience(username: str, goal: str, limit: int = 3) -> str:
    """Past strategies relevant to this goal, for context injection."""
    try:
        words = [w.lower() for w in goal.split() if len(w) > 4][:6]
        if not words:
            return ""
        with _conn() as con:
            clause = " OR ".join("lower(problem) LIKE ?" for _ in words)
            rows = con.execute(
                "SELECT id, problem, strategy, lesson FROM experiences "
                "WHERE username=? AND (%s) ORDER BY uses DESC, id DESC LIMIT ?" % clause,
                [username] + ["%%%s%%" % w for w in words] + [limit]).fetchall()
            if rows:
                con.executemany("UPDATE experiences SET uses=uses+1 WHERE id=?",
                                [(r["id"],) for r in rows])
        return "\n".join("PAST EXPERIENCE: for '%s' -> %s (%s)"
                          % (r["problem"][:80], r["strategy"], r["lesson"])
                          for r in rows)
    except Exception as e:
        log.debug("experience recall failed: %s", e)
        return ""


def list_experiences(username: str, limit: int = 30) -> list:
    with _conn() as con:
        return [dict(r) for r in con.execute(
            "SELECT * FROM experiences WHERE username=? ORDER BY id DESC LIMIT ?",
            (username, limit)).fetchall()]
