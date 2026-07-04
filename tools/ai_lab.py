"""
tools/ai_lab.py -- prompt-engineering laboratory.

Run one prompt across several models/providers, compare outputs, let an AI
judge pick the winner, and store the experiment.
"""
import json
import os
import sqlite3
import time
import logging

log = logging.getLogger("tools.ai_lab")

NAME        = "ai_lab"
DESCRIPTION = ("AI Laboratory: run a prompt across multiple models, compare "
               "results side by side, AI-judge the winner, store the experiment. "
               "Actions: run (prompt, models comma-sep), history.")
CATEGORY = "builtin"
ICON     = "flask"
INPUTS = [
    {"name": "action",  "label": "Action", "type": "select",
     "options": [{"value": "run", "label": "Run experiment"},
                 {"value": "history", "label": "Past experiments"}], "required": True},
    {"name": "prompt",  "label": "Prompt", "type": "textarea"},
    {"name": "models",  "label": "Models (comma-sep)", "type": "text",
     "placeholder": "gpt-4o, gpt-4o-mini"},
    {"name": "username", "label": "Username", "type": "text"},
]

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "aiaurum.db")


def _conn():
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("""CREATE TABLE IF NOT EXISTS lab_experiments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username   TEXT NOT NULL,
        prompt     TEXT NOT NULL,
        results    TEXT NOT NULL,
        winner     TEXT DEFAULT '',
        created_at INTEGER DEFAULT (strftime('%s','now')))""")
    return con


def run(action: str = "run", prompt: str = "", models: str = "",
        username: str = "default") -> dict:
    con = _conn()
    try:
        if action == "history":
            rows = con.execute(
                "SELECT id, prompt, winner, created_at FROM lab_experiments "
                "WHERE username=? ORDER BY id DESC LIMIT 15", (username,)).fetchall()
            return {"result": "\n".join(
                "Experiment #%d: %s -> winner: %s" % (r["id"], r["prompt"][:60], r["winner"])
                for r in rows) or "No experiments yet."}

        if not prompt.strip():
            return {"error": "prompt required"}
        from providers import AI
        model_list = [m.strip() for m in (models or "gpt-4o,gpt-4o-mini").split(",") if m.strip()][:4]

        results = []
        for m in model_list:
            t0 = time.time()
            out = AI.generate(prompt, model=m, max_tokens=700, temperature=0.4)
            results.append({"model": m, "output": out,
                            "latency_s": round(time.time() - t0, 1)})

        judge = AI.generate(
            "You are judging model outputs for the prompt below. Pick the best "
            'one. Reply ONLY JSON: {"winner": "<model>", "reason": "..."}\n\n'
            "PROMPT: %s\n\n%s" % (prompt, "\n\n".join(
                "=== %s ===\n%s" % (r["model"], r["output"][:1500]) for r in results)),
            model="gpt-4o-mini", max_tokens=150, temperature=0.1)
        import re
        m = re.search(r"\{[\s\S]*\}", judge)
        verdict = json.loads(m.group(0)) if m else {"winner": "?", "reason": ""}

        cur = con.execute(
            "INSERT INTO lab_experiments (username, prompt, results, winner) VALUES (?,?,?,?)",
            (username, prompt[:500], json.dumps(results)[:8000], verdict.get("winner", "?")))
        con.commit()

        report = ["# Experiment #%d" % cur.lastrowid, "**Prompt:** " + prompt[:200], ""]
        for r in results:
            report.append("## %s (%.1fs)\n%s\n" % (r["model"], r["latency_s"],
                                                     r["output"][:800]))
        report.append("## Winner: %s\n%s" % (verdict.get("winner"), verdict.get("reason", "")))
        return {"result": "\n".join(report), "winner": verdict.get("winner")}
    finally:
        con.close()
