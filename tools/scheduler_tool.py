"""
Scheduler tool — schedule tasks to run at a specific time or on a recurring schedule.
Uses APScheduler running in the background inside smith_web.py.
"""
import os, json, uuid, datetime, logging

log = logging.getLogger(__name__)

NAME        = "scheduler_tool"
DESCRIPTION = (
    "Schedule a task or reminder to run at a specific time or on a recurring schedule. "
    "Examples: 'remind me to call John at 3pm', 'run web_search every morning at 8am', "
    "'check weather every day at 7am'. "
    "Use action='add' to create, 'list' to view, 'remove' to delete a scheduled task."
)
CATEGORY    = "builtin"
ICON        = "⏰"
INPUTS = [
    {"name": "action",      "label": "Action",       "type": "select",
     "options": [{"value":"add","label":"Add task"},{"value":"list","label":"List tasks"},{"value":"remove","label":"Remove task"}],
     "required": True},
    {"name": "task_name",   "label": "Task name / description", "type": "text",
     "placeholder": "Check weather, Remind me to exercise..."},
    {"name": "schedule",    "label": "When / Schedule", "type": "text",
     "placeholder": "every day at 8am  |  in 30 minutes  |  2025-01-15 14:00  |  every monday at 9am"},
    {"name": "task_action", "label": "What to do (tool name + args as JSON)", "type": "text",
     "placeholder": 'weather  or  {"tool":"web_search","query":"AI news"}'},
    {"name": "task_id",     "label": "Task ID (for remove)", "type": "text"},
]

# ── Shared scheduler registry (populated by smith_web.py on startup) ──────────
_scheduler      = None   # APScheduler instance, set by smith_web.py
_pending_jobs   = []     # queued before scheduler is ready


def set_scheduler(sched):
    global _scheduler
    _scheduler = sched
    for job_kwargs in _pending_jobs:
        _add_job(**job_kwargs)
    _pending_jobs.clear()


def _parse_schedule(schedule_str: str):
    """
    Parse human-readable schedule into APScheduler trigger args.
    Returns (trigger_type, trigger_kwargs) or raises ValueError.
    """
    import re
    s = schedule_str.lower().strip()

    # "in X minutes/hours/seconds"
    m = re.match(r"in\s+(\d+)\s*(second|minute|hour|day)s?", s)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        run_at  = datetime.datetime.now() + datetime.timedelta(**{unit+"s": n})
        return "date", {"run_date": run_at}

    # "every day at HH:MM" / "every morning at 8am"
    m = re.match(r"every\s+(day|morning|evening|night|hour|minute)", s)
    if m:
        period = m.group(1)
        hour, minute = 8, 0   # default morning
        if period == "evening": hour = 18
        if period == "night":   hour = 21
        if period == "hour":    return "interval", {"hours": 1}
        if period == "minute":  return "interval", {"minutes": 1}
        tm = re.search(r"at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", s)
        if tm:
            hour   = int(tm.group(1))
            minute = int(tm.group(2) or 0)
            if tm.group(3) == "pm" and hour < 12: hour += 12
            if tm.group(3) == "am" and hour == 12: hour = 0
        return "cron", {"hour": hour, "minute": minute}

    # "every monday/tuesday/... at HH:MM"
    days = {"monday":0,"tuesday":1,"wednesday":2,"thursday":3,
            "friday":4,"saturday":5,"sunday":6}
    for day, dow in days.items():
        if day in s:
            hour, minute = 9, 0
            tm = re.search(r"at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", s)
            if tm:
                hour   = int(tm.group(1))
                minute = int(tm.group(2) or 0)
                if tm.group(3) == "pm" and hour < 12: hour += 12
                if tm.group(3) == "am" and hour == 12: hour = 0
            return "cron", {"day_of_week": dow, "hour": hour, "minute": minute}

    # "YYYY-MM-DD HH:MM" exact datetime
    m = re.match(r"(\d{4}-\d{2}-\d{2})\s+(\d{1,2}:\d{2})", s)
    if m:
        dt = datetime.datetime.strptime(m.group(1)+" "+m.group(2), "%Y-%m-%d %H:%M")
        return "date", {"run_date": dt}

    # "HH:MM" today
    m = re.match(r"(\d{1,2}):(\d{2})\s*(am|pm)?$", s)
    if m:
        hour   = int(m.group(1))
        minute = int(m.group(2))
        if m.group(3) == "pm" and hour < 12: hour += 12
        if m.group(3) == "am" and hour == 12: hour = 0
        now = datetime.datetime.now()
        dt  = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if dt < now:
            dt += datetime.timedelta(days=1)
        return "date", {"run_date": dt}

    raise ValueError(f"Could not parse schedule: '{schedule_str}'. "
                     "Try: 'in 30 minutes', 'every day at 8am', 'every monday at 9am', '2025-01-15 14:00'")


def _add_job(job_id, task_name, task_action, trigger_type, trigger_kwargs):
    if _scheduler is None:
        _pending_jobs.append(dict(job_id=job_id, task_name=task_name,
                                  task_action=task_action,
                                  trigger_type=trigger_type,
                                  trigger_kwargs=trigger_kwargs))
        return

    def _execute():
        import tools as _t
        try:
            if isinstance(task_action, dict):
                tool_name = task_action.pop("tool", None)
                if tool_name:
                    result = _t.call(tool_name, **task_action)
                    log.info("scheduler: %s result=%s", task_name, result)
            else:
                log.info("scheduler reminder: %s", task_name)
                try:
                    from plyer import notification
                    notification.notify(title="Assist Neo Reminder",
                                        message=task_name, timeout=10)
                except Exception:
                    pass
        except Exception as ex:
            log.error("scheduler execute failed: %s — %s", task_name, ex)

    log.info("scheduler: adding job id=%s name=%s trigger=%s kwargs=%s", job_id, task_name, trigger_type, trigger_kwargs)
    _scheduler.add_job(_execute, trigger_type, id=job_id,
                       replace_existing=True, **trigger_kwargs)


def run(action: str, task_name: str = "", schedule: str = "",
        task_action: str = "", task_id: str = "") -> dict:

    if action == "list":
        if _scheduler is None:
            return {"message": "⚠️ Scheduler not running. Restart Assist Neo."}
        jobs = _scheduler.get_jobs()
        if not jobs:
            return {"message": "No scheduled tasks."}
        lines = []
        for j in jobs:
            next_run = str(j.next_run_time)[:19] if j.next_run_time else "N/A"
            lines.append(f"• **{j.id}** — next run: {next_run}")
        return {"message": "**Scheduled tasks:**\n" + "\n".join(lines)}

    if action == "remove":
        if not task_id:
            return {"error": "Provide task_id to remove."}
        if _scheduler is None:
            return {"error": "Scheduler not running."}
        try:
            _scheduler.remove_job(task_id)
            return {"message": f"✅ Removed scheduled task: `{task_id}`"}
        except Exception as e:
            log.warning("scheduler remove_job failed: %s", e)
            return {"error": f"Could not remove job: {e}"}

    if action == "add":
        if not task_name:
            return {"error": "task_name is required."}
        if not schedule:
            return {"error": "schedule is required (e.g. 'every day at 8am', 'in 30 minutes')."}

        try:
            trigger_type, trigger_kwargs = _parse_schedule(schedule)
        except ValueError as e:
            return {"error": str(e)}

        job_id = task_id or uuid.uuid4().hex[:8]

        # Parse task_action
        parsed_action = task_action.strip()
        if parsed_action.startswith("{"):
            try:
                parsed_action = json.loads(parsed_action)
            except Exception:
                pass

        _add_job(job_id, task_name, parsed_action, trigger_type, trigger_kwargs)

        # Human-readable next run
        if trigger_type == "date":
            when = str(trigger_kwargs["run_date"])[:19]
            repeat = "once"
        elif trigger_type == "interval":
            hrs  = trigger_kwargs.get("hours", 0)
            mins = trigger_kwargs.get("minutes", 0)
            when = f"every {hrs}h {mins}m" if hrs else f"every {mins} minutes"
            repeat = "recurring"
        else:
            h = trigger_kwargs.get("hour", "?")
            m = trigger_kwargs.get("minute", 0)
            dow = trigger_kwargs.get("day_of_week", "daily")
            when = f"{'daily' if dow == 'daily' else dow} at {h:02d}:{m:02d}"
            repeat = "recurring"

        return {"message": f"✅ Scheduled: **{task_name}**\n"
                           f"• ID: `{job_id}`\n"
                           f"• When: {when} ({repeat})\n"
                           f"• Action: {task_action or 'notification reminder'}"}

    return {"error": f"Unknown action: {action}"}
