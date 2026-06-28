"""
services/auth_service.py -- user authentication helpers
"""
import os, json, hashlib, secrets, logging
from functools import wraps
from flask import session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

log = logging.getLogger("services.auth")

_BASE       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_USERS_FILE = os.path.join(_BASE, "users.json")
_SECRET_FILE = os.path.join(_BASE, ".secret_key")


# -- Secret key ----------------------------------------------------------------

def get_secret_key() -> str:
    env = os.getenv("SECRET_KEY")
    if env:
        return env
    if os.path.exists(_SECRET_FILE):
        with open(_SECRET_FILE) as f:
            return f.read().strip()
    key = secrets.token_hex(32)
    with open(_SECRET_FILE, "w") as f:
        f.write(key)
    return key


# -- User store ----------------------------------------------------------------

def load_users() -> dict:
    try:
        with open(_USERS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.warning("Could not load users: %s", e)
        return {}


def save_users(users: dict) -> None:
    with open(_USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)


def hash_password(pw: str) -> str:
    return generate_password_hash(pw)


def check_password(pw: str, stored: str) -> bool:
    """Support both modern werkzeug hashes and legacy SHA-256."""
    if stored.startswith("pbkdf2:") or stored.startswith("scrypt:"):
        return check_password_hash(stored, pw)
    return hashlib.sha256(pw.encode()).hexdigest() == stored


# -- Session helpers -----------------------------------------------------------

def current_user() -> str:
    return session.get("username", "")


def current_nick() -> str:
    return session.get("nickname", current_user().capitalize())


def is_authenticated() -> bool:
    return bool(session.get("auth"))


# -- Role helpers --------------------------------------------------------------

def current_role() -> str:
    """Return the role stored in the session ('user', 'admin', etc.)."""
    return session.get("role", "user")


def is_admin() -> bool:
    return current_role() == "admin"


# -- Decorators ----------------------------------------------------------------

def login_required(f):
    """Route decorator -- returns 401 JSON if not authenticated."""
    @wraps(f)
    def _wrap(*args, **kwargs):
        if not session.get("auth"):
            return jsonify({"error": "login required"}), 401
        return f(*args, **kwargs)
    return _wrap


def require_role(*roles: str):
    """
    Route decorator -- requires the user to have one of the given roles.
    Usage:
        @require_role("admin")
        def admin_route(): ...
    """
    def decorator(f):
        @wraps(f)
        def _wrap(*args, **kwargs):
            if not session.get("auth"):
                return jsonify({"error": "login required"}), 401
            user_role = session.get("role", "user")
            if user_role not in roles:
                log.warning(
                    "Permission denied: user=%s role=%s required=%s endpoint=%s",
                    session.get("username"), user_role, roles, f.__name__,
                )
                return jsonify({"error": "Permission denied", "required_role": list(roles)}), 403
            return f(*args, **kwargs)
        return _wrap
    return decorator
