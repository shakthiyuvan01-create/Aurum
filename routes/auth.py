"""
routes/auth.py — login, register, logout
"""
import logging
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


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect("/login")
