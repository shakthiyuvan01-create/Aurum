"""Web routes for Gamification system (XP, levels, ranks)."""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from services.gamification import (
    XP_EVENTS,
    award_xp,
    get_leaderboard,
    get_recent_activity,
    get_stats,
    rank_for_level,
    reset_user,
    xp_progress,
    xp_for_level,
)

logger = logging.getLogger(__name__)

gamification_bp = Blueprint("gamification", __name__, url_prefix="/api/gamification")


@gamification_bp.route("/<username>", methods=["GET"])
def stats(username: str):
    """Get gamification stats for a user."""
    return jsonify({"success": True, "stats": get_stats(username)})


@gamification_bp.route("/<username>/award", methods=["POST"])
def award(username: str):
    """Award XP for an event."""
    data = request.get_json(force=True) or {}
    event = data.get("event", "")
    multiplier = data.get("multiplier", 1.0)
    result = award_xp(username, event, float(multiplier))
    return jsonify({"success": True, **result})


@gamification_bp.route("/events", methods=["GET"])
def list_events():
    """List all XP events and their values."""
    return jsonify({
        "success": True,
        "events": XP_EVENTS,
    })


@gamification_bp.route("/leaderboard", methods=["GET"])
def leaderboard():
    """Get top users by XP."""
    limit = request.args.get("limit", 20, type=int)
    return jsonify({
        "success": True,
        "leaderboard": get_leaderboard(limit),
    })


@gamification_bp.route("/<username>/activity", methods=["GET"])
def activity(username: str):
    """Get recent XP activity for a user."""
    limit = request.args.get("limit", 20, type=int)
    return jsonify({
        "success": True,
        "activity": get_recent_activity(username, limit),
    })


@gamification_bp.route("/<username>/reset", methods=["POST"])
def reset(username: str):
    """Reset a user's gamification data."""
    return jsonify(reset_user(username))
