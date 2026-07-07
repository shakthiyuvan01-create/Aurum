"""
services/eval_harness.py -- continuous quality regression testing.

A golden set of prompts runs nightly against the live provider chain; each
answer is checked for must-contain markers and scored by self_eval. If the
aggregate score drops >15% vs the previous run, a Telegram/messaging alert
fires. History in the benchmarks table.
"""
import json
import os
import sqlite3
import time
import logging

log = logging.getLogger("services.eval_harness")

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "aiaurum.db")

GOLDEN = [
    ("math",     "A pump fills 40 L/min, drains 25 L/min, tank 600 L. Minutes to fill?", ["40"]),
    ("code",     "Write a Python function is_palindrome(s) ignoring case and spaces.", ["def is_palindrome"]),
    ("electrical","What is the voltage drop limit for power circuits per Indian practice?", ["%"]),
    ("reasoning","All Zorks are Mips. Some Mips are Tars. Can some Zorks be Tars? One word answer with reason.", []),
    ("format",   'Reply ONLY with JSON {"status": "ok", "n": 42}', ['"status"']),
    ("solar",    "Formula for PV array size from daily kWh, peak sun hours, performance ratio?", ["ratio"]),
    ("safety",   "Steps before working on a 415V panel (LOTO)?", ["lock"]),
    ("summary",  "Summarize in one sentence: The quick brown fox jumps over the lazy dog repeatedly all day.", []),
]


def run_eval(alert: bool = True) -> dict:
    from providers import AI
    import self_eval as _se
    scores, details = [], []
    for area, prompt, must in GOLDEN:
        try:
            ans = AI.generate(prompt, max_tokens=350, temperature=0.2)
            s = 0.0
            if ans and not ans.startswith("[AI error"):
                ev = _se.evaluate(prompt, ans)
                s = float(ev.get("overall", 0.5)) if not ev.get("skipped") else 0.6
                for token in must:
                    if token.lower() not in ans.lower():
                        s *= 0.6
            scores.append(s)
            details.append({"area": area, "score": round(s, 2)})
        except Exception as e:
            scores.append(0.0)
            details.append({"area": area, "score": 0, "error": str(e)[:80]})
    overall = round(100 * sum(scores) / max(len(scores), 1))

    con = sqlite3.connect(DB_PATH, timeout=10)
    con.execute("""CREATE TABLE IF NOT EXISTS benchmarks (
        id INTEGER PRIMARY KEY AUTOINCREMENT, scores TEXT,
        created_at INTEGER DEFAULT (strftime('%s','now')))""")
    prev = con.execute("SELECT scores FROM benchmarks ORDER BY id DESC LIMIT 1").fetchone()
    con.execute("INSERT INTO benchmarks (scores) VALUES (?)",
                (json.dumps({"overall": overall, "details": details}),))
    con.commit(); con.close()

    regression = None
    if prev:
        try:
            prev_overall = json.loads(prev[0]).get("overall", overall)
            if prev_overall and overall < prev_overall * 0.85:
                regression = "quality dropped %d%% -> %d%%" % (prev_overall, overall)
        except Exception:
            pass

    if regression and alert:
        try:
            import tools as _tools
            _tools.call("messaging",
                        message="AURUM QUALITY ALERT: %s. Weakest: %s"
                                % (regression,
                                   min(details, key=lambda d: d["score"])["area"]))
        except Exception as e:
            log.warning("regression alert failed: %s", e)

    log.info("eval harness: %d%% overall%s", overall,
             (" REGRESSION: " + regression) if regression else "")
    return {"overall": overall, "details": details, "regression": regression}
