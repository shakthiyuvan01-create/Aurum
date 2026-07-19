"""
services/permission_manager.py -- gate dangerous capabilities.

Usage in any tool/route:

    from services.permission_manager import perms
    if not perms.check("shell"):
        return {"error": "Permission denied: shell execution is disabled. Enable it in Settings > Permissions."}

Persisted to permissions.json in the project root. Everything defaults to
allowed except the most dangerous capabilities.
"""
import json
import os
import threading
import logging

log = logging.getLogger("services.permissions")

_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "permissions.json")

DEFAULTS = {
    "browser":        True,    # Playwright browser automation
    "shell":          True,    # execute shell / python code
    "files_write":    True,    # workspace file writes
    "files_delete":   False,   # deleting files
    "packages":       False,   # pip/npm installs
    "messaging":      True,   # sending messages (Telegram etc.)
    "network":        True,    # outbound web requests from tools
    "self_improve":   False,   # autonomous self-improvement loop (suggestions only)
    "background_ai":  True,    # ambient intelligence: KG extraction, predictions, experience learning
    "self_extend":    False,   # tool forge: AI writes + registers new tools
    "heartbeat":      False,   # autonomous self-maintenance (updates own memory)
}


class PermissionManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._perms = dict(DEFAULTS)
        self._load()

    def _load(self):
        try:
            if os.path.exists(_PATH):
                with open(_PATH) as f:
                    saved = json.load(f)
                self._perms.update({k: bool(v) for k, v in saved.items() if k in DEFAULTS})
        except Exception as e:
            log.warning("could not load permissions: %s", e)

    def _save(self):
        try:
            with open(_PATH, "w") as f:
                json.dump(self._perms, f, indent=2)
        except Exception as e:
            log.warning("could not save permissions: %s", e)

    def check(self, capability: str) -> bool:
        return self._perms.get(capability, False)

    def deny_message(self, capability: str) -> dict:
        return {"error": "Permission denied: '%s' is disabled. "
                         "Enable it via POST /permissions." % capability}

    def set(self, capability: str, allowed: bool) -> bool:
        if capability not in DEFAULTS:
            return False
        with self._lock:
            self._perms[capability] = bool(allowed)
            self._save()
        log.info("permission %s -> %s", capability, allowed)
        return True

    def all(self) -> dict:
        return dict(self._perms)


perms = PermissionManager()
