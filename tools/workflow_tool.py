"""
Workflow / Task Chain tool — define and run sequences of tool calls as named workflows.
Workflows are stored in SQLite and can be triggered by name or by the agent.
"""
import os, json, sqlite3, logging

log = logging.getLogger(__name__)

NAME        = "workflow_tool"
DESCRIPTION = (
    "Create and run workflows — named sequences of tool calls that execute in order. "
    "Example: a 'morning briefing' workflow runs weather + news + calendar every morning. "
    "Use action='create' to define a workflow, 'run' to execute it, 'list' to see all, 'delete' to remove."
)
CATEGORY    = "builtin"
ICON        = "⚡"
INPUTS = [
    {"name": "action",        "label": "Action", "type": "select",
     "options": [{"value":"create","label":"Create workflow"},{"value":"run","label":"Run workflow"},
                 {"value":"list","label":"List workflows"},{"value":"delete","label":"Delete workflow"}],
     "required": True},
    {"name": "workflow_name", "label": "Workflow name",  "type": "text",
     "placeholder": "morning briefing, daily report..."},
    {"name": "steps",         "label": "Steps (JSON array)", "type": "textarea",
     "placeholder": '[{"tool":"weather","city":"London"},{"tool":"news","topic":"AI"},{"tool":"calendar","action":"list"}]'},
    {"name": "description",   "label": "Description", "type": "text",
     "placeholder": "What this workflow does"},
]

_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "aiaurum.db")


def _conn():
    c = sqlite3.connect(_DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("""CREATE TABLE IF NOT EXISTS workflows (
        name        TEXT PRIMARY KEY,
        description TEXT,
        steps       TEXT,
        created_at  TEXT DEFAULT (datetime('now'))
    )""")
    c.commit()
    return c


def run(action: str, workflow_name: str = "", steps: str = "",
        description: str = "") -> dict:
    import tools as _tools

    # ── List ──────────────────────────────────────────────────────────────────
    if action == "list":
        with _conn() as c:
            rows = c.execute("SELECT name, description, steps FROM workflows ORDER BY name").fetchall()
        if not rows:
            return {"message": "No workflows defined yet. Use action='create' to build one."}
        lines = []
        for r in rows:
            try:
                n_steps = len(json.loads(r["steps"]))
            except Exception:
                n_steps = "?"  # display fallback, not an error
            desc = r["description"] or ""
            lines.append(f"• **{r['name']}** ({n_steps} steps){' — ' + desc if desc else ''}")
        return {"message": "**Saved workflows:**\n" + "\n".join(lines)}

    # ── Delete ────────────────────────────────────────────────────────────────
    if action == "delete":
        if not workflow_name:
            return {"error": "workflow_name is required."}
        with _conn() as c:
            c.execute("DELETE FROM workflows WHERE name=?", (workflow_name,))
        return {"message": f"✅ Deleted workflow: **{workflow_name}**"}

    # ── Create ────────────────────────────────────────────────────────────────
    if action == "create":
        if not workflow_name:
            return {"error": "workflow_name is required."}
        if not steps:
            return {"error": "steps (JSON array) is required."}
        try:
            steps_list = json.loads(steps)
            if not isinstance(steps_list, list):
                raise ValueError("steps must be a JSON array")
        except Exception as e:
            return {"error": f"Invalid steps JSON: {e}\n"
                             "Example: [{\"tool\":\"weather\",\"city\":\"London\"},{\"tool\":\"news\",\"topic\":\"AI\"}]"}

        log.info("workflow create: name=%s steps=%d", workflow_name, len(steps_list))
        with _conn() as c:
            c.execute("INSERT OR REPLACE INTO workflows(name,description,steps) VALUES(?,?,?)",
                      (workflow_name, description, json.dumps(steps_list)))
        return {"message": f"✅ Workflow **{workflow_name}** created with {len(steps_list)} steps!\n"
                           f"Run it with: `workflow_tool(action='run', workflow_name='{workflow_name}')`"}

    # ── Run ───────────────────────────────────────────────────────────────────
    if action == "run":
        if not workflow_name:
            return {"error": "workflow_name is required."}
        with _conn() as c:
            row = c.execute("SELECT steps FROM workflows WHERE name=?", (workflow_name,)).fetchone()
        if not row:
            return {"error": f"Workflow '{workflow_name}' not found. Use action='list' to see available workflows."}

        steps_list = json.loads(row["steps"])
        log.info("workflow run: name=%s steps=%d", workflow_name, len(steps_list))
        results    = []
        errors     = []

        for i, step in enumerate(steps_list, 1):
            if not isinstance(step, dict):
                errors.append(f"Step {i}: invalid format (must be a dict)")
                continue
            tool_name = step.pop("tool", None)
            if not tool_name:
                errors.append(f"Step {i}: missing 'tool' key")
                continue
            try:
                log.debug("workflow step %d: tool=%s args=%s", i, tool_name, step)
                result = _tools.call(tool_name, **step)
                # Extract message from result dict
                if isinstance(result, dict):
                    msg = result.get("message") or result.get("output") or result.get("result") or str(result)
                else:
                    msg = str(result)
                results.append(f"**Step {i} — {tool_name}:**\n{msg[:500]}")
            except Exception as e:
                log.error("workflow step %d tool=%s failed: %s", i, tool_name, e)
                errors.append(f"Step {i} ({tool_name}) failed: {e}")

        output = f"## ⚡ Workflow: {workflow_name}\n\n"
        output += "\n\n---\n\n".join(results)
        if errors:
            output += "\n\n**Errors:**\n" + "\n".join("• " + e for e in errors)

        return {"message": output}

    return {"error": f"Unknown action: {action}. Use: create, run, list, delete"}
