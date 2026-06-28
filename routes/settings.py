"""
routes/settings.py — personality settings, model routing prefs
"""
import logging
from flask import Blueprint, request, jsonify
from services.auth_service import login_required, current_user

settings_bp = Blueprint("settings", __name__)
log = logging.getLogger("routes.settings")

_deps: dict = {}

def _init(deps: dict) -> None:
    _deps.update(deps)

def _db():
    return _deps["db"]


@settings_bp.route("/settings/personality", methods=["GET", "POST"])
@login_required
def personality_route():
    log.info("settings: user=%s method=%s", current_user(), request.method)
    uname = current_user()
    db    = _db()
    if request.method == "GET":
        return jsonify(db.get_settings(uname))
    body = request.json or {}
    db.save_settings(
        uname,
        persona_name        = body.get("persona_name", ""),
        custom_instructions = body.get("custom_instructions", ""),
        model_routing       = int(body.get("model_routing", 1)),
        self_reflect        = int(body.get("self_reflect", 0)),
    )
    return jsonify({"ok": True})
