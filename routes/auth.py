"""
routes/auth.py — login, register, logout, guest
"""
import uuid, logging
from flask import Blueprint, request, session, redirect, jsonify, render_template
from services.auth_service import load_users, hash_password, check_password, login_required

auth_bp = Blueprint("auth", __name__)
log = logging.getLogger("routes.auth")

_deps: dict = {}

def _init(deps: dict) -> None:
    _deps.update(deps)

def _db():
    return _deps["db"]


# ── login page helpers ────────────────────────────────────────────────────────

def _login_page(err=""):
    return render_template("login.html", err=err)

def _register_page(err=""):
    return render_template("register.html", err=err)


# ── routes ────────────────────────────────────────────────────────────────────

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    log.info("login attempt: method=%s json=%s", request.method, request.is_json)
    if request.method == "POST":
        db = _db()
        un = ((request.json or {}).get("username", "") if request.is_json
              else request.form.get("username", "")).strip().lower()
        pw = ((request.json or {}).get("password", "") if request.is_json
              else request.form.get("password", ""))
        stored = db.get_user(un)
        if un and stored and check_password(pw, stored["pw_hash"]):
            # Two-factor: if enabled for this account, require a valid TOTP code
            try:
                from services.twofa import status as _2fa_status, check_login as _2fa_check
                if _2fa_status(un).get("enabled"):
                    code = ((request.json or {}).get("totp", "") if request.is_json
                            else request.form.get("totp", ""))
                    if not _2fa_check(un, code):
                        msg = "2FA code required" if not code else "Invalid 2FA code"
                        if request.is_json:
                            return jsonify({"error": msg, "needs_2fa": True}), 401
                        return _login_page(msg)
            except Exception as _2e:
                log.debug("2fa check skipped: %s", _2e)
            nick = stored.get("nick", un.capitalize())
            role = stored.get("role", "user")
            # bootstrap: first registered user or ADMIN_USERNAMES env → admin
            try:
                from config import cfg
                if un in cfg.ADMIN_USERNAMES and role != "admin":
                    db.set_user_role(un, "admin")
                    role = "admin"
            except Exception:
                pass
            session["auth"]     = True
            session["username"] = un
            session["nickname"] = nick
            session["role"]     = role
            session.permanent   = True
            if request.is_json:
                return jsonify({"ok": True, "role": role})
            return redirect("/")
        err = "Wrong username or password."
        if request.is_json:
            return jsonify({"error": err}), 401
        return _login_page(err)
    return _login_page()


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    log.info("register attempt: method=%s", request.method)
    if request.method == "POST":
        db  = _db()
        un  = ((request.json or {}).get("username", "") if request.is_json
               else request.form.get("username", "")).strip().lower()
        pw  = ((request.json or {}).get("password", "") if request.is_json
               else request.form.get("password", ""))
        nick = ((request.json or {}).get("nickname", "") if request.is_json
                else request.form.get("nickname", "")).strip()
        if not nick:
            nick = un.capitalize()

        err = ""
        if not un or not pw:
            err = "Please fill in all fields."
        elif len(un) < 3:
            err = "Username must be at least 3 characters."
        elif len(pw) < 8:
            err = "Password must be at least 8 characters."
        elif db.get_user(un):
            err = "Username already taken."
        else:
            # First user ever → auto-admin; otherwise normal 'user' role
            try:
                from config import cfg
                role = "admin" if un in cfg.ADMIN_USERNAMES else "user"
            except Exception:
                role = "user"
            db.create_user(un, nick, hash_password(pw), role=role)
            session["auth"]     = True
            session["username"] = un
            session["nickname"] = nick
            session["role"]     = role
            session.permanent   = True
            if request.is_json:
                return jsonify({"ok": True, "role": role})
            return redirect("/")

        if request.is_json:
            return jsonify({"error": err}), 400
        return _register_page(err)
    return _register_page()


@auth_bp.route("/guest", methods=["GET", "POST"])
def guest_login():
    """
    One-click guest access -- no account needed.
    Creates an ephemeral session with role='guest'.
    Guest sessions expire when the browser closes (not permanent).
    """
    log.info("guest login from %s", request.remote_addr)
    guest_id = "guest_" + uuid.uuid4().hex[:8]
    session["auth"]     = True
    session["username"] = guest_id
    session["nickname"] = "Guest"
    session["role"]     = "guest"
    session["is_guest"] = True
    session.permanent   = False   # expires on browser close
    if request.is_json:
        return jsonify({"ok": True, "role": "guest", "username": guest_id})
    return redirect("/")


# ── Google OAuth (Sign in with Google) ───────────────────────────────────────
import os as _os, secrets as _secrets, urllib.parse as _uparse

def _google_redirect_uri():
    base = _os.getenv("OAUTH_REDIRECT_BASE", "").strip().rstrip("/")
    if not base:
        base = request.url_root.rstrip("/")
        host = request.host.split(":")[0]
        # anything that is not localhost is served over https in practice
        if host not in ("localhost", "127.0.0.1") and base.startswith("http://"):
            base = "https://" + base[len("http://"):]
    return base + "/auth/google/callback"


@auth_bp.route("/auth/google")
def google_login():
    cid = _os.getenv("GOOGLE_CLIENT_ID", "")
    if not cid:
        return _login_page("Google login not configured (set GOOGLE_CLIENT_ID).")
    state = _secrets.token_urlsafe(16)
    session["_oauth_state"] = state
    redirect_uri = _google_redirect_uri()
    params = {
        "client_id": cid,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    return redirect("https://accounts.google.com/o/oauth2/v2/auth?" +
                    _uparse.urlencode(params))


@auth_bp.route("/auth/google/callback")
def google_callback():
    import requests as _rq
    cid = _os.getenv("GOOGLE_CLIENT_ID", "")
    csec = _os.getenv("GOOGLE_CLIENT_SECRET", "")
    if request.args.get("state") != session.pop("_oauth_state", None):
        return _login_page("Google login failed: state mismatch. Try again.")
    code = request.args.get("code", "")
    if not code:
        return _login_page("Google login cancelled.")
    redirect_uri = _google_redirect_uri()
    try:
        tok = _rq.post("https://oauth2.googleapis.com/token", data={
            "code": code, "client_id": cid, "client_secret": csec,
            "redirect_uri": redirect_uri, "grant_type": "authorization_code",
        }, timeout=20).json()
        access = tok.get("access_token")
        if not access:
            return _login_page("Google login failed: no token.")
        info = _rq.get("https://www.googleapis.com/oauth2/v2/userinfo",
                       headers={"Authorization": "Bearer " + access}, timeout=20).json()
    except Exception as e:
        log.error("google oauth: %s", e)
        return _login_page("Google login error. Try again.")

    email = (info.get("email") or "").strip().lower()
    if not email or not info.get("verified_email", True):
        return _login_page("Google account has no verified email.")
    nick = info.get("name") or email.split("@")[0]
    db = _db()
    stored = db.get_user(email)
    if not stored:
        # create a passwordless account (random hash; they log in via Google)
        db.create_user(email, nick, hash_password(_secrets.token_urlsafe(32)))
        stored = db.get_user(email)
    role = (stored or {}).get("role", "user")
    try:
        from config import cfg
        if email in cfg.ADMIN_USERNAMES and role != "admin":
            db.set_user_role(email, "admin"); role = "admin"
    except Exception:
        pass
    session["auth"] = True
    session["username"] = email
    session["nickname"] = nick
    session["role"] = role
    session["via"] = "google"
    session["avatar"] = info.get("picture", "")
    session.permanent = True
    log.info("google login: %s", email)
    return redirect("/")


@auth_bp.route("/auth/google/enabled")
def google_enabled():
    return jsonify({"enabled": bool(_os.getenv("GOOGLE_CLIENT_ID", ""))})


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@auth_bp.route("/csrf-token")
@login_required
def csrf_token():
    """Return the current CSRF token so the frontend can attach it to requests."""
    import secrets
    if not session.get("_csrf_token"):
        session["_csrf_token"] = secrets.token_hex(24)
    return jsonify({"csrf_token": session["_csrf_token"]})


@auth_bp.route("/2fa/status")
@login_required
def twofa_status():
    from services.twofa import status
    return jsonify(status(session.get("username", "")))


@auth_bp.route("/2fa/enroll", methods=["POST"])
@login_required
def twofa_enroll():
    from services.twofa import enroll
    return jsonify(enroll(session.get("username", "")))


@auth_bp.route("/2fa/confirm", methods=["POST"])
@login_required
def twofa_confirm():
    from services.twofa import confirm
    code = (request.get_json(force=True) or {}).get("code", "")
    return jsonify(confirm(session.get("username", ""), code))


@auth_bp.route("/2fa/disable", methods=["POST"])
@login_required
def twofa_disable():
    from services.twofa import disable
    return jsonify(disable(session.get("username", "")))
