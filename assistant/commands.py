"""assistant/commands.py — handle_personal, handle_commands, handle_basics."""
import ast as _ast
import datetime
import logging
import re

from assistant.config import ASSISTANT_NAME, USER_NAME
from assistant.memory import (
    save_neo_memory, get_memory, clear_memory,
    load_memory, save_memory, user_name,
)
from assistant.speech import say

log = logging.getLogger("assistant.commands")


def _after(text: str, prefixes) -> str:
    for p in prefixes:
        if text.startswith(p):
            return text[len(p):].strip()
    return ""


def time_greeting() -> str:
    h = datetime.datetime.now().hour
    if h < 12:  return "Good morning"
    if h < 17:  return "Good afternoon"
    if h < 21:  return "Good evening"
    return "Good night"


def greet() -> None:
    name = user_name()
    say(f"{time_greeting()}{', ' + name if name else ''}! How can I help you today?")


def handle_personal(text: str) -> bool:
    low = text.lower().strip()

    # Greeting
    if low in ("hi","hello","hey","yo","sup","good morning","good afternoon","good evening","good night"):
        greet()
        return True

    # Name queries
    if any(k in low for k in ("what's your name","what is your name","who are you","your name")):
        say(f"I am {ASSISTANT_NAME}, your personal AI assistant.")
        return True

    # Memory: remember X
    r = _after(low, ("remember ","memorize ","note that ","don't forget "))
    if r:
        save_neo_memory(r)
        say(f"Got it, I'll remember: {r}")
        return True

    # Memory: recall
    if any(k in low for k in ("what do you remember","recall everything","show memory","list memories")):
        mems = get_memory()
        say("Here's what I remember: " + "; ".join(mems) if mems else "I don't have any saved memories yet.")
        return True

    # Memory: forget
    if any(k in low for k in ("forget everything","clear memory","reset memory")):
        clear_memory()
        say("Memory cleared.")
        return True

    return False


def translate(text: str) -> None:
    from assistant.models import ask_ai_brain
    reply = ask_ai_brain(
        "Act as a translator. " + text +
        ". Reply with only the translation, plus a simple pronunciation if helpful.")
    say(reply or "I couldn't translate that.")


def _clean_what(s: str) -> str:
    s = s.strip(" .,")
    if s.lower().startswith("to "):
        s = s[3:]
    return s or "your reminder"


def _parse_when(text: str):
    import time as _t
    low = text.lower()
    now = datetime.datetime.now()

    m = re.search(r"\bin\s+(\d+)\s*(seconds?|secs?|minutes?|mins?|hours?|hrs?)\b", low)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        secs = n * (3600 if unit.startswith(("hour","hr")) else 1 if unit.startswith("sec") else 60)
        what = re.sub(r"\bin\s+\d+\s*\w+\b", "", text).strip()
        return (_t.time() + secs, _clean_what(what))

    m = re.search(r"\bat\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", low)
    if m:
        h, mins, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3)
        if ap == "pm" and h < 12: h += 12
        if ap == "am" and h == 12: h = 0
        due = now.replace(hour=h % 24, minute=mins, second=0, microsecond=0)
        if due <= now:
            due += datetime.timedelta(days=1)
        what = re.sub(r"\bat\s+\d{1,2}(?::\d{2})?\s*(am|pm)?\b", "", text, flags=re.I).strip()
        return (due.timestamp(), _clean_what(what))

    return (None, text)


def add_reminder(text: str) -> None:
    due, what = _parse_when(text)
    if not due:
        say("When should I remind you? Try: remind me to call mom at 6 pm.")
        return
    mem = load_memory()
    mem.setdefault("reminders", []).append({"text": what, "due": due})
    save_memory(mem)
    when = datetime.datetime.fromtimestamp(due).strftime("%I:%M %p")
    name = user_name()
    say(f"Okay{', ' + name if name else ''}, I'll remind you to {what} at {when}.")


def _reminder_watcher() -> None:
    import time as _t
    from assistant.speech import alert
    while True:
        try:
            mem = load_memory()
            rem = mem.get("reminders", [])
            now = _t.time()
            due = [r for r in rem if r.get("due", 0) <= now]
            if due:
                for r in due:
                    alert("Reminder", r.get("text", "reminder"))
                mem["reminders"] = [r for r in rem if r.get("due", 0) > now]
                save_memory(mem)
        except Exception:
            pass
        _t.sleep(15)


def start_reminder_watcher() -> None:
    import threading
    threading.Thread(target=_reminder_watcher, daemon=True).start()


def handle_commands(text: str) -> bool:
    low = text.lower().strip()
    r = _after(low, ("remind me to ","remind me ","set a reminder to ",
                     "set a reminder ","set an alarm to ","set an alarm "))
    if r:
        add_reminder(r)
        return True
    if low.startswith("translate ") or "how do you say" in low or "how do i say" in low:
        translate(text)
        return True
    return False


def handle_basics(text: str) -> bool:
    low = text.lower().strip()

    if any(k in low for k in ("what time","what's the time","whats the time",
                              "current time","the time now","tell me the time")):
        say("It's " + datetime.datetime.now().strftime("%I:%M %p") + ".")
        return True

    if any(k in low for k in ("what's the date","what is the date","todays date",
                              "today's date","what day is it","what's today","what is today")):
        say("Today is " + datetime.datetime.now().strftime("%A, %d %B %Y") + ".")
        return True

    expr = low
    for word, sym in (("multiplied by","*"),("divided by","/"),
                      ("plus","+"),("minus","-"),("times","*")):
        expr = expr.replace(word, sym)
    expr = re.sub(r"(what is|whats|what's|calculate|compute|how much is)", "", expr).strip(" ?")
    if expr and re.fullmatch(r"[0-9\.\s\+\-\*\/\(\)]+", expr):
        try:
            _allowed = (_ast.Expression,_ast.BinOp,_ast.UnaryOp,_ast.Constant,
                        _ast.Add,_ast.Sub,_ast.Mult,_ast.Div,_ast.Pow,_ast.Mod,
                        _ast.FloorDiv,_ast.USub,_ast.UAdd,_ast.Load)
            _tree = _ast.parse(expr, mode="eval")
            for _n in _ast.walk(_tree):
                if not isinstance(_n, _allowed):
                    raise ValueError("disallowed node")
            say(f"That's {eval(compile(_tree, '<calc>', 'eval'), {'__builtins__': {}}, {})}.")
            return True
        except Exception:
            pass
    return False
