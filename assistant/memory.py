"""assistant/memory.py — SQLite-backed memory helpers."""
import json
import logging
import os
from assistant.config import ASSISTANT_NAME

log = logging.getLogger("assistant.memory")

_DEFAULT_USER = "default"
_MEMORY_FILE  = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "memory.json")


def _db():
    import db
    return db


def save_neo_memory(fact: str, username: str = _DEFAULT_USER) -> None:
    try:
        _db().save_memory(username, fact)
    except Exception as e:
        log.error("save_neo_memory failed: %s", e)


def get_memory(username: str = _DEFAULT_USER) -> list:
    try:
        return _db().get_memories(username) or []
    except Exception as e:
        log.error("get_memory failed: %s", e)
        return []


def clear_memory(username: str = _DEFAULT_USER) -> None:
    try:
        _db().clear_memories(username)
    except Exception as e:
        log.error("clear_memory failed: %s", e)


def _memory_context(username: str = _DEFAULT_USER) -> str:
    mems = get_memory(username)
    if not mems:
        return ""
    return "\n\nThings you remember about this user:\n" + "\n".join(f"- {m}" for m in mems)


def load_memory(username: str = _DEFAULT_USER) -> dict:
    try:
        return json.loads(_db().get_raw_memory(username) or "{}")
    except Exception:
        pass
    try:
        with open(_MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_memory(mem: dict, username: str = _DEFAULT_USER) -> None:
    try:
        _db().set_raw_memory(username, json.dumps(mem))
    except Exception:
        try:
            with open(_MEMORY_FILE, "w", encoding="utf-8") as f:
                json.dump(mem, f, indent=2)
        except Exception as e:
            log.error("save_memory failed: %s", e)


def user_name() -> str:
    from assistant.config import USER_NAME
    return USER_NAME
