"""
services/error_handler.py — Centralised exception classes + Flask error handlers
==================================================================================
Usage in routes:
    from services.error_handler import BadRequest, NotFound, Forbidden
    raise BadRequest("invalid input")

Register with Flask in app.py:
    from services.error_handler import register_error_handlers
    register_error_handlers(app)

All errors return consistent JSON:
    {"error": "<message>", "code": <status_int>}
"""
from __future__ import annotations
import logging
from flask import jsonify, Flask

log = logging.getLogger("error_handler")


# ── Typed application exceptions ─────────────────────────────────────────────

class AppError(Exception):
    """Base class — all AI Aurum exceptions inherit from this."""
    status_code: int = 500
    default_message: str = "An unexpected error occurred."

    def __init__(self, message: str | None = None, payload: dict | None = None):
        super().__init__(message or self.default_message)
        self.message = message or self.default_message
        self.payload = payload or {}

    def to_response(self):
        body = {"error": self.message, "code": self.status_code}
        body.update(self.payload)
        return jsonify(body), self.status_code


class BadRequest(AppError):
    """400 — malformed input, missing required field."""
    status_code    = 400
    default_message = "Bad request."


class Unauthorized(AppError):
    """401 — not authenticated."""
    status_code    = 401
    default_message = "Authentication required."


class Forbidden(AppError):
    """403 — authenticated but lacks permission."""
    status_code    = 403
    default_message = "You do not have permission to perform this action."


class NotFound(AppError):
    """404 — resource does not exist."""
    status_code    = 404
    default_message = "Resource not found."


class Conflict(AppError):
    """409 — duplicate resource / state conflict."""
    status_code    = 409
    default_message = "Conflict — resource already exists."


class UnprocessableEntity(AppError):
    """422 — semantically invalid payload."""
    status_code    = 422
    default_message = "Unprocessable entity."


class TooManyRequests(AppError):
    """429 — rate limit exceeded."""
    status_code    = 429
    default_message = "Too many requests. Please slow down."


class ServiceUnavailable(AppError):
    """503 — downstream dependency (LLM API, tool, DB) is down."""
    status_code    = 503
    default_message = "Service temporarily unavailable."


# ── Flask error handler registration ─────────────────────────────────────────

def register_error_handlers(app: Flask) -> None:
    """Call once in app.py after creating the Flask instance."""

    # ── Our typed AppErrors ───────────────────────────────────────────────────
    @app.errorhandler(AppError)
    def handle_app_error(err: AppError):
        log.warning("AppError %d: %s", err.status_code, err.message)
        return err.to_response()

    # ── Standard HTTP errors ─────────────────────────────────────────────────
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": str(e), "code": 400}), 400

    @app.errorhandler(401)
    def unauthorized(e):
        return jsonify({"error": "Authentication required.", "code": 401}), 401

    @app.errorhandler(403)
    def forbidden(e):
        return jsonify({"error": "Forbidden.", "code": 403}), 403

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found.", "code": 404}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"error": "Method not allowed.", "code": 405}), 405

    @app.errorhandler(413)
    def payload_too_large(e):
        return jsonify({"error": "File too large.", "code": 413}), 413

    @app.errorhandler(429)
    def too_many_requests(e):
        return jsonify({"error": "Rate limit exceeded.", "code": 429}), 429

    @app.errorhandler(500)
    def internal_error(e):
        log.exception("Unhandled 500: %s", e)
        return jsonify({"error": "Internal server error.", "code": 500}), 500

    @app.errorhandler(Exception)
    def unhandled_exception(e):
        # catch-all — prevent stack traces leaking to clients
        log.exception("Unhandled exception: %s", e)
        return jsonify({"error": "An unexpected error occurred.", "code": 500}), 500

    log.info("Error handlers registered")
