"""
tools/simulator.py -- simulate destructive operations before doing them.

"Delete folder X" -> shows exactly what WOULD be deleted (file counts by type,
total size) and requires an explicit confirmed=true run to actually do it.
"""
import os
import shutil
import logging
from collections import Counter

log = logging.getLogger("tools.simulator")

NAME        = "simulator"
DESCRIPTION = ("Simulate before acting: preview exactly what a destructive "
               "operation would do. Actions: delete_folder (path) previews "
               "counts/size; pass confirmed=true to execute after previewing.")
CATEGORY = "builtin"
ICON     = "shield"
INPUTS = [
    {"name": "action",    "label": "Action", "type": "select",
     "options": [{"value": "delete_folder", "label": "Delete folder"}], "required": True},
    {"name": "path",      "label": "Path", "type": "text", "required": True},
    {"name": "confirmed", "label": "Actually do it (true/false)", "type": "text"},
    {"name": "username",  "label": "Username", "type": "text"},
]

_KINDS = {".png": "images", ".jpg": "images", ".jpeg": "images", ".gif": "images",
          ".doc": "documents", ".docx": "documents", ".pdf": "documents",
          ".txt": "documents", ".md": "documents", ".xlsx": "spreadsheets",
          ".csv": "spreadsheets", ".py": "code", ".js": "code", ".html": "code"}


def run(action: str = "delete_folder", path: str = "", confirmed: str = "false",
        username: str = "default") -> dict:
    if action != "delete_folder":
        return {"error": "unknown action"}
    if not path or not os.path.isdir(path):
        return {"error": "folder not found: %s" % path}
    base = os.path.normpath(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    target = os.path.normpath(os.path.abspath(path))
    if not target.startswith(base) or target == base:
        return {"error": "simulator only operates inside the project folder"}

    counts, total, size = Counter(), 0, 0
    for dirpath, dirs, files in os.walk(target):
        for f in files:
            total += 1
            counts[_KINDS.get(os.path.splitext(f)[1].lower(), "other")] += 1
            try:
                size += os.path.getsize(os.path.join(dirpath, f))
            except OSError:
                pass

    breakdown = "\n".join("- %d %s" % (n, k) for k, n in counts.most_common())
    preview = ("SIMULATION: deleting `%s` will remove\n\n- **%d files** (%.1f MB)\n%s"
               % (path, total, size / 1048576, breakdown))

    if str(confirmed).lower() in ("true", "1", "yes"):
        from services.permission_manager import perms
        if not perms.check("files_delete"):
            return perms.deny_message("files_delete")
        shutil.rmtree(target)
        return {"result": preview + "\n\n**EXECUTED** - folder deleted.", "deleted": total}
    return {"result": preview + "\n\nRun again with confirmed=true to proceed.",
            "simulated": True}
