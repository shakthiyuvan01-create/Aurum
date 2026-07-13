"""
services/twofa.py -- TOTP two-factor auth (authenticator apps).

Pure-stdlib RFC-6238 TOTP (no pyotp dependency). Enroll -> scan the otpauth://
URI in Google Authenticator/Authy -> verify. Secret stored per user in SQLite.
"""
import base64
import hashlib
import hmac
import os
import sqlite3
import struct
import time
import logging

log = logging.getLogger("services.twofa")

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "aiaurum.db")


def _con():
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.execute("""CREATE TABLE IF NOT EXISTS twofa (
        username TEXT PRIMARY KEY, secret TEXT, enabled INTEGER DEFAULT 0)""")
    return con


def _b32(secret: str) -> bytes:
    return base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True)


def totp(secret: str, when: float = None, step: int = 30, digits: int = 6) -> str:
    when = when if when is not None else time.time()
    counter = struct.pack(">Q", int(when // step))
    h = hmac.new(_b32(secret), counter, hashlib.sha1).digest()
    off = h[-1] & 0x0F
    code = (struct.unpack(">I", h[off:off + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return str(code).zfill(digits)


def verify(secret: str, code: str) -> bool:
    code = (code or "").strip().replace(" ", "")
    now = time.time()
    # accept the current and adjacent windows (clock skew tolerance)
    return any(totp(secret, now + d) == code for d in (-30, 0, 30))


def status(username: str) -> dict:
    with _con() as con:
        r = con.execute("SELECT enabled FROM twofa WHERE username=?",
                        (username,)).fetchone()
    return {"enabled": bool(r[0]) if r else False}


def enroll(username: str, issuer: str = "AI Aurum") -> dict:
    secret = base64.b32encode(os.urandom(20)).decode().rstrip("=")
    with _con() as con:
        con.execute("INSERT OR REPLACE INTO twofa (username, secret, enabled) "
                    "VALUES (?,?,0)", (username, secret))
        con.commit()
    uri = "otpauth://totp/%s:%s?secret=%s&issuer=%s" % (issuer, username, secret, issuer)
    return {"secret": secret, "otpauth_uri": uri,
            "note": "Add to your authenticator app, then confirm a code to enable."}


def confirm(username: str, code: str) -> dict:
    with _con() as con:
        r = con.execute("SELECT secret FROM twofa WHERE username=?",
                        (username,)).fetchone()
        if not r:
            return {"error": "enroll first"}
        if not verify(r[0], code):
            return {"error": "code invalid - check the app and try again"}
        con.execute("UPDATE twofa SET enabled=1 WHERE username=?", (username,))
        con.commit()
    return {"ok": True, "enabled": True}


def disable(username: str) -> dict:
    with _con() as con:
        con.execute("DELETE FROM twofa WHERE username=?", (username,))
        con.commit()
    return {"ok": True, "enabled": False}


def check_login(username: str, code: str) -> bool:
    """Called during login: True if 2FA off, or on and the code is valid."""
    with _con() as con:
        r = con.execute("SELECT secret, enabled FROM twofa WHERE username=?",
                        (username,)).fetchone()
    if not r or not r[1]:
        return True
    return verify(r[0], code)
