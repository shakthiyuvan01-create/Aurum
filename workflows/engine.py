"""
workflows/engine.py — AI Workflow Builder engine.
Reusable multi-step workflows stored in SQLite.
Each workflow: name, description, steps (trigger → action → condition → next).
"""
from __future__ import annotations
import json, logging, os, sqlite3, time, uuid
from contextlib import contextmanager
from typing import Any

log = logging.getLogger("workflows")

_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "aiaurum.db")


@contextmanager
def _conn():
    con = sqlite3.connect(_DB)
    con.row_factory = sqlite3.Row
    con.execute("""CREATE TABLE IF NOT EXISTS workflows (
        id TEXT PRIMARY KEY,
        username TEXT NOT NULL,
        name TEXT NOT NULL,
        description TEXT DEFAULT \'\',
        steps TEXT NOT NULL DEFAULT \'[]\',
        schedule TEXT DEFAULT \'\',
        enabled INTEGER DEFAULT 1,
        run_count INTEGER DEFAULT 0,
        last_run INTEGER DEFAULT 0,
        created_at INTEGER DEFAULT (strftime('%s','now'))
    )""")
    con.execute("CREATE INDEX IF NOT EXISTS idx_wf_user ON workflows(username)")
    con.commit()
    try:
        yield con
        con.commit()
    finally:
        con.close()


# ── CRUD ──────────────────────────────────────────────────────────────────────
def create_workflow(username: str, name: str, description: str, steps: list, schedule: str = "") -> dict:
    wf_id = uuid.uuid4().hex[:12]
    with _conn() as con:
        con.execute(
            "INSERT INTO workflows(id,username,name,description,steps,schedule) VALUES(?,?,?,?,?,?)",
            (wf_id, username, name, description, json.dumps(steps), schedule),
        )
    return {"id": wf_id, "name": name}


def get_workflow(wf_id: str, username: str) -> dict | None:
    with _conn() as con:
        row = con.execute("SELECT * FROM workflows WHERE id=? AND username=?", (wf_id, username)).fetchone()
        if row:
            d = dict(row)
            d["steps"] = json.loads(d.get("steps", "[]"))
            return d
    return None


def list_workflows(username: str) -> list[dict]:
    with _conn() as con:
        rows = con.execute("SELECT * FROM workflows WHERE username=? ORDER BY created_at DESC", (username,)).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["steps"] = json.loads(d.get("steps", "[]"))
            result.append(d)
        return result


def delete_workflow(wf_id: str, username: str) -> bool:
    with _conn() as con:
        c = con.execute("DELETE FROM workflows WHERE id=? AND username=?", (wf_id, username))
        return c.rowcount > 0


# ── Execution ─────────────────────────────────────────────────────────────────
def run_workflow(wf_id: str, username: str, trigger_data: dict = None) -> dict:
    """Execute a workflow step by step. Returns {ok, steps_run, results, error}."""
    wf = get_workflow(wf_id, username)
    if not wf:
        return {"error": "Workflow not found"}

    steps    = wf.get("steps", [])
    results  = []
    context  = trigger_data or {}

    for i, step in enumerate(steps):
        step_type = step.get("type", "tool")
        try:
            if step_type == "tool":
                import tools as _tools
                tool_name = step.get("tool", "")
                params    = {**step.get("params", {}), **context, "username": username}
                result    = _tools.call(tool_name, **params)
                context.update(result)
                results.append({"step": i+1, "type": "tool", "tool": tool_name, "result": result})

            elif step_type == "agent":
                import agents as _agents
                agent_name = step.get("agent", "researcher")
                task       = step.get("task", "").format(**context)
                agent      = _agents.get_agent(agent_name, username)
                output     = agent.think(task)
                context["last_output"] = output
                results.append({"step": i+1, "type": "agent", "agent": agent_name, "result": output[:400]})

            elif step_type == "message":
                import tools as _tools
                platform = step.get("platform", "telegram")
                message  = step.get("message", "").format(**context)
                r = _tools.call("messaging", platform=platform, message=message, username=username)
                results.append({"step": i+1, "type": "message", "platform": platform, "result": r})

            elif step_type == "condition":
                condition_key = step.get("key", "")
                condition_val = step.get("value", "")
                actual        = str(context.get(condition_key, ""))
                met           = actual == str(condition_val)
                results.append({"step": i+1, "type": "condition", "met": met})
                if not met and step.get("stop_on_fail", False):
                    break

            elif step_type == "wait":
                import time as _t
                _t.sleep(min(step.get("seconds", 1), 60))
                results.append({"step": i+1, "type": "wait"})

        except Exception as e:
            results.append({"step": i+1, "error": str(e)})
            if step.get("stop_on_error", True):
                break

    with _conn() as con:
        con.execute(
            "UPDATE workflows SET run_count=run_count+1, last_run=? WHERE id=?",
            (int(time.time()), wf_id)
        )

    return {"ok": True, "steps_run": len(results), "results": results}


def workflow_from_description(description: str, username: str) -> dict:
    """
    Use AI to generate a workflow from a natural language description.
    Returns the created workflow dict.
    """
    token = os.getenv("GITHUB_TOKEN", "")
    if not token:
        return {"error": "GITHUB_TOKEN not set"}

    prompt = f"""Create a workflow for: {description}

Return ONLY valid JSON:
{{
  "name": "Short workflow name",
  "description": "What this workflow does",
  "schedule": "cron expression or empty",
  "steps": [
    {{
      "type": "tool|agent|message|condition|wait",
      "tool": "tool_name (if type=tool)",
      "params": {{}},
      "agent": "agent_name (if type=agent)",
      "task": "task description (if type=agent)",
      "platform": "telegram (if type=message)",
      "message": "message text (if type=message)",
      "key": "context_key (if type=condition)",
      "value": "expected_value (if type=condition)",
      "seconds": 5
    }}
  ]
}}

Available tools: web_search, news, weather, email_tool, messaging, youtube, calculator, reminders
Available agents: researcher, programmer, planner, automation"""

    try:
        import requests
        r = requests.post(
            "https://models.inference.ai.azure.com/chat/completions",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "You create structured JSON workflows. Output JSON only."},
                    {"role": "user",   "content": prompt},
                ],
                "max_tokens": 800,
                "temperature": 0.3,
            },
            timeout=30,
        )
        raw   = r.json()["choices"][0]["message"]["content"].strip()
        clean = raw.lstrip("```json").lstrip("```").rstrip("```").strip()
        data  = json.loads(clean)
    except Exception as e:
        return {"error": str(e)}

    wf = create_workflow(
        username    = username,
        name        = data.get("name", description[:40]),
        description = data.get("description", description),
        steps       = data.get("steps", []),
        schedule    = data.get("schedule", ""),
    )
    wf["steps"] = data.get("steps", [])
    return wf
