"""
services/snapshots.py -- auto-snapshot files before edits/deletes so a bad
/vibe or agent write is reversible. Copies land in workspace/.snapshots/.
Keeps the last N versions per file.
"""
import os
import shutil
import time
import logging

log = logging.getLogger("services.snapshots")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAP_DIR = os.path.join(BASE, "workspace", ".snapshots")
KEEP = 10


def snapshot(full_path: str, reason: str = "edit") -> str:
    """Copy the current file (if it exists) into the snapshot store. No-op for
    new files. Returns the snapshot id or ''."""
    try:
        if not os.path.isfile(full_path):
            return ""
        os.makedirs(SNAP_DIR, exist_ok=True)
        rel = os.path.relpath(full_path, BASE).replace(os.sep, "__")
        snap_id = "%s@@%d@@%s" % (rel, int(time.time()), reason)
        shutil.copy2(full_path, os.path.join(SNAP_DIR, snap_id))
        # prune old versions of this file
        versions = sorted(f for f in os.listdir(SNAP_DIR) if f.startswith(rel + "@@"))
        for old in versions[:-KEEP]:
            try:
                os.remove(os.path.join(SNAP_DIR, old))
            except OSError:
                pass
        return snap_id
    except Exception as e:
        log.debug("snapshot failed: %s", e)
        return ""


def list_snapshots(limit: int = 40) -> list:
    if not os.path.isdir(SNAP_DIR):
        return []
    out = []
    for f in sorted(os.listdir(SNAP_DIR), reverse=True)[:limit]:
        parts = f.split("@@")
        if len(parts) >= 3:
            out.append({"id": f, "file": parts[0].replace("__", "/"),
                        "when": int(parts[1]), "reason": parts[2]})
    return out


def restore(snap_id: str) -> dict:
    src = os.path.join(SNAP_DIR, snap_id)
    if not os.path.isfile(src):
        return {"error": "snapshot not found"}
    rel = snap_id.split("@@")[0].replace("__", os.sep)
    dst = os.path.join(BASE, rel)
    try:
        snapshot(dst, reason="pre-restore")  # so restore is itself undoable
        shutil.copy2(src, dst)
        return {"ok": True, "restored": rel}
    except Exception as e:
        return {"error": str(e)}
