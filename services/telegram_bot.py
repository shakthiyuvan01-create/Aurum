"""
services/telegram_bot.py -- talk to Aurum from Telegram.

Set TELEGRAM_BOT_TOKEN (from @BotFather) and TELEGRAM_ALLOWED_IDS
(comma-separated chat IDs; message the bot once and check logs for your id).
A background thread long-polls getUpdates and answers through the full
provider chain with your memory context.
"""
import os
import threading
import time
import logging
import requests

log = logging.getLogger("services.telegram_bot")

_API = "https://api.telegram.org/bot{token}/{method}"
_started = False


def _allowed(chat_id: str) -> bool:
    ids = os.getenv("TELEGRAM_ALLOWED_IDS", "")
    return not ids or str(chat_id) in [i.strip() for i in ids.split(",")]


def _answer(text: str, username: str) -> str:
    try:
        from providers import AI
        from services.memory_api import memory
        ctx = memory.context(username, text)
        sys_p = ("You are AI Aurum answering via Telegram. Be concise. "
                 + ("\n\nContext about the user:\n" + ctx if ctx else ""))
        return AI.generate(text, system=sys_p, max_tokens=900, temperature=0.4)[:3900]
    except Exception as e:
        return "Error: %s" % e


def _loop(token: str):
    offset = 0
    log.info("telegram bot polling started")
    while True:
        try:
            r = requests.get(_API.format(token=token, method="getUpdates"),
                             params={"timeout": 50, "offset": offset}, timeout=60)
            for upd in r.json().get("result", []):
                offset = upd["update_id"] + 1
                msg = upd.get("message") or {}
                chat_id = (msg.get("chat") or {}).get("id")
                text = (msg.get("text") or "").strip()
                if not chat_id or not text:
                    continue
                if not _allowed(chat_id):
                    log.warning("telegram: unauthorized chat_id %s (add to "
                                "TELEGRAM_ALLOWED_IDS to allow)", chat_id)
                    continue
                uname = os.getenv("TELEGRAM_USER", "default")
                reply = _answer(text, uname)
                requests.post(_API.format(token=token, method="sendMessage"),
                              json={"chat_id": chat_id, "text": reply}, timeout=30)
        except Exception as e:
            log.debug("telegram poll error: %s", e)
            time.sleep(10)


def start():
    global _started
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token or _started:
        return False
    _started = True
    threading.Thread(target=_loop, args=(token,), daemon=True).start()
    return True
