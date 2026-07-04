"""
routes/canvas_routes.py -- dynamic document canvas.

Collaborative doc workspace: save docs, keep version history, and let the
AI revise a highlighted selection in place.
"""
import os
import sqlite3
import logging
from flask import Blueprint, request, jsonify, session
from services.auth_service import login_required

canvas_bp = Blueprint("canvas", __name__)
log = logging.getLogger("routes.canvas")

_deps: dict = {}

def _init(deps: dict) -> None:
    _deps.update(deps)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "aiaurum.db")


def _conn():
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.executescript("""
        CREATE TABLE IF NOT EXISTS canvas_docs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username   TEXT NOT NULL,
            title      TEXT NOT NULL DEFAULT 'Untitled',
            content    TEXT NOT NULL DEFAULT '',
            updated_at INTEGER DEFAULT (strftime('%s','now')));
        CREATE TABLE IF NOT EXISTS canvas_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id     INTEGER NOT NULL,
            content    TEXT NOT NULL,
            note       TEXT DEFAULT '',
            created_at INTEGER DEFAULT (strftime('%s','now')));
    """)
    return con


def _user():
    return session.get("username", "guest")


@canvas_bp.route("/canvas/docs")
@login_required
def canvas_list():
    with _conn() as con:
        rows = con.execute(
            "SELECT id, title, updated_at FROM canvas_docs WHERE username=? "
            "ORDER BY updated_at DESC", (_user(),)).fetchall()
    return jsonify({"docs": [dict(r) for r in rows]})


@canvas_bp.route("/canvas/docs", methods=["POST"])
@login_required
def canvas_save():
    body    = request.get_json(force=True) or {}
    doc_id  = body.get("doc_id")
    title   = (body.get("title") or "Untitled").strip()[:120]
    content = body.get("content") or ""
    with _conn() as con:
        if doc_id:
            old = con.execute("SELECT content FROM canvas_docs WHERE id=? AND username=?",
                              (doc_id, _user())).fetchone()
            if old is None:
                return jsonify({"error": "not found"}), 404
            if old["content"] != content:
                con.execute("INSERT INTO canvas_versions (doc_id, content, note) VALUES (?,?,?)",
                            (doc_id, old["content"], body.get("note", "auto")))
            con.execute("UPDATE canvas_docs SET title=?, content=?, "
                        "updated_at=strftime('%s','now') WHERE id=?",
                        (title, content, doc_id))
            return jsonify({"ok": True, "doc_id": doc_id})
        cur = con.execute("INSERT INTO canvas_docs (username, title, content) VALUES (?,?,?)",
                          (_user(), title, content))
        return jsonify({"ok": True, "doc_id": cur.lastrowid})


@canvas_bp.route("/canvas/docs/<int:doc_id>")
@login_required
def canvas_get(doc_id):
    with _conn() as con:
        row = con.execute("SELECT * FROM canvas_docs WHERE id=? AND username=?",
                          (doc_id, _user())).fetchone()
        if not row:
            return jsonify({"error": "not found"}), 404
        versions = con.execute(
            "SELECT id, note, created_at, length(content) AS size FROM canvas_versions "
            "WHERE doc_id=? ORDER BY id DESC LIMIT 20", (doc_id,)).fetchall()
    return jsonify({"doc": dict(row), "versions": [dict(v) for v in versions]})


@canvas_bp.route("/canvas/versions/<int:version_id>")
@login_required
def canvas_version(version_id):
    with _conn() as con:
        row = con.execute(
            "SELECT v.* FROM canvas_versions v JOIN canvas_docs d ON d.id=v.doc_id "
            "WHERE v.id=? AND d.username=?", (version_id, _user())).fetchone()
    if not row:
        return jsonify({"error": "not found"}), 404
    return jsonify({"version": dict(row)})


@canvas_bp.route("/canvas/docs/<int:doc_id>", methods=["DELETE"])
@login_required
def canvas_delete(doc_id):
    with _conn() as con:
        con.execute("DELETE FROM canvas_versions WHERE doc_id=?", (doc_id,))
        con.execute("DELETE FROM canvas_docs WHERE id=? AND username=?", (doc_id, _user()))
    return jsonify({"ok": True})


@canvas_bp.route("/canvas/revise", methods=["POST"])
@login_required
def canvas_revise():
    """AI revision of a highlighted selection (or the whole doc)."""
    body        = request.get_json(force=True) or {}
    selection   = body.get("selection") or ""
    instruction = (body.get("instruction") or "improve clarity").strip()
    context     = body.get("context") or ""
    if not selection.strip():
        return jsonify({"error": "selection required"}), 400
    from providers import AI
    revised = AI.generate(
        "Revise ONLY the selected passage according to the instruction. "
        "Return ONLY the revised passage - no preamble, no quotes.\n\n"
        "INSTRUCTION: %s\n\nDOCUMENT CONTEXT (for tone/consistency):\n%s\n\n"
        "SELECTED PASSAGE:\n%s" % (instruction, context[:3000], selection[:6000]),
        model="gpt-4o", max_tokens=1500, temperature=0.3)
    if revised.startswith("[AI error"):
        return jsonify({"error": revised}), 502
    return jsonify({"ok": True, "revised": revised})
