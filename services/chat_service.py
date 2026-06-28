"""
services/chat_service.py — chat history helpers (SQLite-backed via db module)
"""
import os, json, logging
import db as _db

log = logging.getLogger("services.chat")


def save_chat(cid: str, uname: str, title: str, messages: list) -> None:
    """Persist chat to SQLite."""
    try:
        _db.save_chat(cid, uname, title, messages)
    except Exception as e:
        log.error("save_chat failed: %s", e)


def load_chat(cid: str) -> dict | None:
    """Load chat by ID from SQLite."""
    return _db.get_chat(cid)


def list_chats(uname: str) -> list:
    """List all chats for a user."""
    try:
        return _db.list_chats(uname)
    except Exception as e:
        log.error("list_chats failed: %s", e)
        return []


def delete_chat(cid: str, uname: str) -> None:
    _db.delete_chat(cid, uname)


def rename_chat(cid: str, uname: str, title: str) -> None:
    _db.rename_chat(cid, uname, title)
