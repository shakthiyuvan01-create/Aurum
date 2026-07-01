"""
tools/skill_manager.py — Self-Evolving Skills for AI Aurum
===========================================================
Lets the AI save, search, and reuse solution patterns (skills) across sessions.
When the AI solves a complex problem it can save the approach as a reusable skill.
Future queries search skills first so proven patterns are reused automatically.
"""
import uuid, logging
import db as _db

NAME        = "skill_manager"
DESCRIPTION = (
    "Save, search, and retrieve reusable skill documents. "
    "Use save_skill when you've solved a complex problem that others might face. "
    "Use search_skills before starting a complex task to find relevant prior solutions."
)
CATEGORY    = "memory"
ICON        = "🧠"
INPUTS = [
    {"name": "action",      "label": "Action",      "type": "select",
     "options": ["save_skill", "search_skills", "list_skills", "delete_skill"],
     "required": True},
    {"name": "name",        "label": "Skill Name",  "type": "text",   "required": False},
    {"name": "description", "label": "Description", "type": "text",   "required": False},
    {"name": "content",     "label": "Skill Content","type": "textarea","required": False},
    {"name": "tags",        "label": "Tags (comma-separated)", "type": "text", "required": False},
    {"name": "query",       "label": "Search Query", "type": "text",  "required": False},
    {"name": "skill_id",    "label": "Skill ID",    "type": "text",   "required": False},
]

log = logging.getLogger("tools.skill_manager")


def run(action: str = "", name: str = "", description: str = "",
        content: str = "", tags: str = "", query: str = "",
        skill_id: str = "", username: str = "default", **_) -> str:

    action = (action or "").strip().lower()

    # ── save_skill ─────────────────────────────────────────────────────────────
    if action == "save_skill":
        if not name or not content:
            return "❌ name and content are required to save a skill."
        sid     = skill_id or str(uuid.uuid4())[:8]
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        _db.save_skill(username, sid, name.strip(), description.strip(),
                       content.strip(), tag_list)
        log.info("skill saved: %s (%s) for user %s", name, sid, username)
        return (f"✅ Skill **{name}** saved (id: `{sid}`).\n"
                f"Tags: {', '.join(tag_list) if tag_list else 'none'}\n\n"
                f"This skill will be retrieved automatically in future relevant sessions.")

    # ── search_skills ──────────────────────────────────────────────────────────
    if action == "search_skills":
        if not query:
            return "❌ query is required to search skills."
        results = _db.search_skills(username, query, limit=5)
        if not results:
            return f"No saved skills match '{query}'."
        lines = [f"🔍 Found {len(results)} skill(s) matching '{query}':\n"]
        for s in results:
            lines.append(
                f"### {s['name']} (id: `{s['id']}`)\n"
                f"**{s['description']}**\n"
                f"Tags: {', '.join(s['tags']) or 'none'} | Used {s['usage_count']}×\n\n"
                f"{s['content']}\n"
                f"---"
            )
        return "\n".join(lines)

    # ── list_skills ────────────────────────────────────────────────────────────
    if action == "list_skills":
        skills = _db.get_skills(username)
        if not skills:
            return "No skills saved yet. Use save_skill to save your first reusable solution pattern."
        lines = [f"📚 **{len(skills)} saved skill(s):**\n"]
        for s in skills:
            lines.append(
                f"• **{s['name']}** (id:`{s['id']}`) — {s['description'] or 'no description'} "
                f"| Tags: {', '.join(s['tags']) or 'none'} | Used {s['usage_count']}×"
            )
        return "\n".join(lines)

    # ── delete_skill ───────────────────────────────────────────────────────────
    if action == "delete_skill":
        if not skill_id:
            return "❌ skill_id is required to delete a skill."
        _db.delete_skill(skill_id, username)
        return f"🗑️ Skill `{skill_id}` deleted."

    return f"❌ Unknown action '{action}'. Use: save_skill, search_skills, list_skills, delete_skill."
