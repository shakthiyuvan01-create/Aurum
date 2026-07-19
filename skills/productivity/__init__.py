"""Productivity skills — reminders, notes, todos."""
from skills import Skill


def _execute_reminder(text: str, time: str = "later") -> dict:
    try:
        from assistant.commands import add_reminder
        add_reminder(text, time)
        return {"success": True, "reminder": text, "time": time}
    except Exception as e:
        return {"success": False, "error": str(e)}


def register_skill(registry):
    registry.register(Skill(
        name="set_reminder",
        description="Set a reminder for a task",
        execute=_execute_reminder,
        category="productivity",
    ))
