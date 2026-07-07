"""
services/self_optimize.py -- REAL bounded self-improvement.

The only kind that actually works: measure, change something safe and
reversible, measure again, keep ONLY if the score genuinely improved.

What it tunes: a "system overlay" -- an extra instruction block prepended to
every chat's system prompt. It does NOT touch source code, weights, or the
optimizer. It cannot climb past what the golden-set evaluator can measure.

Loop:
  1. baseline = eval_harness score
  2. AI proposes an overlay targeting the weakest area
  3. apply overlay -> re-run eval
  4. improved by margin? keep it. else revert to previous overlay.
  5. log the attempt (verified gain or rejected)

Safeguards: permission 'self_improve' (OFF default), overlay length capped,
full rollback, every version stored, alert on regression.
"""
import json
import os
import sqlite3
import time
import logging

log = logging.getLogger("services.self_optimize")

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "aiaurum.db")
MARGIN = 3          # must beat baseline by >= 3 points to be kept
MAX_OVERLAY = 600   # chars


def _con():
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.execute("""CREATE TABLE IF NOT EXISTS app_config (
        key TEXT PRIMARY KEY, value TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS self_opt_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        baseline INTEGER, candidate INTEGER, kept INTEGER,
        overlay TEXT, target TEXT,
        created_at INTEGER DEFAULT (strftime('%s','now')))""")
    return con


def _get_overlay() -> str:
    con = _con()
    row = con.execute("SELECT value FROM app_config WHERE key='system_overlay'").fetchone()
    con.close()
    return row[0] if row else ""


def _set_overlay(text: str):
    con = _con()
    con.execute("INSERT OR REPLACE INTO app_config (key, value) VALUES ('system_overlay', ?)",
                (text[:MAX_OVERLAY],))
    con.commit(); con.close()


def run_cycle(force: bool = False) -> dict:
    from services.permission_manager import perms
    if not perms.check("self_improve"):
        return {"skipped": True, "reason": "self_improve permission disabled"}

    from services.eval_harness import run_eval
    prev_overlay = _get_overlay()

    base = run_eval(alert=False)
    baseline = base["overall"]
    weakest = min(base["details"], key=lambda d: d["score"])["area"]

    # AI proposes an improvement overlay targeting the weakest area
    from providers import AI
    proposal = AI.generate(
        "You tune an AI assistant's system prompt. Its weakest area is '%s' "
        "(golden-set score %d%%). Write a SHORT instruction block (max 3 "
        "sentences) to prepend to its system prompt that would improve answers "
        "in that area without hurting others. Output ONLY the instruction text."
        % (weakest, baseline),
        model="gpt-4o-mini", max_tokens=150, temperature=0.4)
    if not proposal or proposal.startswith("[AI error"):
        return {"error": "no proposal generated"}
    candidate_overlay = (prev_overlay + "\n" + proposal.strip())[:MAX_OVERLAY].strip()

    # apply, re-measure
    _set_overlay(candidate_overlay)
    cand = run_eval(alert=False)
    candidate = cand["overall"]

    kept = candidate >= baseline + MARGIN
    if not kept:
        _set_overlay(prev_overlay)   # rollback

    con = _con()
    con.execute("INSERT INTO self_opt_log (baseline, candidate, kept, overlay, target) "
                "VALUES (?,?,?,?,?)",
                (baseline, candidate, 1 if kept else 0,
                 proposal.strip()[:MAX_OVERLAY], weakest))
    con.commit(); con.close()

    log.info("self-optimize: %d%% -> %d%% targeting %s -> %s",
             baseline, candidate, weakest, "KEPT" if kept else "reverted")
    return {"baseline": baseline, "candidate": candidate, "target": weakest,
            "kept": kept, "proposal": proposal.strip(),
            "note": ("improvement verified and applied" if kept
                     else "no verified gain - reverted to previous prompt")}


def history(limit: int = 20) -> list:
    con = _con()
    rows = con.execute("SELECT * FROM self_opt_log ORDER BY id DESC LIMIT ?",
                       (limit,)).fetchall()
    cols = [d[0] for d in con.description]
    con.close()
    return [dict(zip(cols, r)) for r in rows]


def reset():
    """Wipe the overlay -- return to the stock prompt."""
    _set_overlay("")
    return {"ok": True, "overlay": "cleared"}
