"""
services/discord_bot.py -- talk to / control Aurum from Discord.

Set DISCORD_BOT_TOKEN (from the Discord Developer Portal, with the MESSAGE
CONTENT intent enabled). Optionally DISCORD_ALLOWED_IDS (comma-separated user
IDs). A background thread connects to the Discord gateway and answers messages
through the full provider chain with your memory context.
"""
import json
import os
import threading
import time
import logging

log = logging.getLogger("services.discord_bot")
_started = False


def _allowed(uid):
    ids = os.getenv("DISCORD_ALLOWED_IDS", "")
    return not ids or str(uid) in [i.strip() for i in ids.split(",")]


def _answer(text, username):
    try:
        from providers import AI
        from services.memory_api import memory
        ctx = memory.context(username, text)
        sysp = ("You are AI Aurum answering via Discord. Be concise."
                + ("\n\nContext:\n" + ctx if ctx else ""))
        return AI.generate(text, system=sysp, max_tokens=900)[:1900]
    except Exception as e:
        return "Error: %s" % e


def _loop(token):
    import requests
    api = "https://discord.com/api/v10"
    hdr = {"Authorization": "Bot " + token, "Content-Type": "application/json"}
    # Gateway via long-poll of messages is not supported; use the simple
    # gateway websocket. Kept dependency-free using websocket handshake.
    try:
        import websocket  # optional
    except Exception:
        log.warning("discord bot needs websocket-client: pip install websocket-client")
        return
    try:
        gw = requests.get(api + "/gateway", timeout=15).json()["url"]
    except Exception as e:
        log.warning("discord gateway fetch failed: %s", e)
        return
    log.info("discord bot connecting...")

    ws = websocket.create_connection(gw + "?v=10&encoding=json", timeout=60)
    hb = None
    seq = None
    try:
        hello = json.loads(ws.recv())
        interval = hello["d"]["heartbeat_interval"] / 1000.0
        ws.send(json.dumps({"op": 2, "d": {"token": token,
                "intents": 1 << 9 | 1 << 15,  # GUILD_MESSAGES + MESSAGE_CONTENT
                "properties": {"os": "linux", "browser": "aurum", "device": "aurum"}}}))

        def _beat():
            while True:
                time.sleep(interval)
                try:
                    ws.send(json.dumps({"op": 1, "d": seq}))
                except Exception:
                    return
        threading.Thread(target=_beat, daemon=True).start()

        while True:
            msg = json.loads(ws.recv())
            seq = msg.get("s") or seq
            if msg.get("t") == "MESSAGE_CREATE":
                d = msg["d"]
                if d.get("author", {}).get("bot"):
                    continue
                content = d.get("content", "").strip()
                uid = d.get("author", {}).get("id")
                chan = d.get("channel_id")
                if not content or not _allowed(uid):
                    continue
                reply = _answer(content, os.getenv("DISCORD_USER", "default"))
                requests.post(api + "/channels/%s/messages" % chan,
                              headers=hdr, json={"content": reply}, timeout=20)
    except Exception as e:
        log.debug("discord loop ended: %s", e)


def start():
    global _started
    token = os.getenv("DISCORD_BOT_TOKEN", "")
    if not token or _started:
        return False
    _started = True
    threading.Thread(target=_loop, args=(token,), daemon=True).start()
    return True
