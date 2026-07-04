"""
tools/messaging.py — Send messages via Telegram Bot API and Discord webhooks.
API-based (no desktop required). Also supports Slack incoming webhooks.
"""
import json
import logging
import os

log = logging.getLogger(__name__)

NAME        = "messaging"
DESCRIPTION = (
    "Send messages via Telegram, Discord, or Slack. "
    "Requires tokens/webhooks set in environment variables."
)
CATEGORY = "communication"
ICON     = "💬"
INPUTS = [
    {"name": "platform", "label": "Platform", "type": "select",
     "options": [
         {"value": "telegram", "label": "Telegram"},
         {"value": "discord",  "label": "Discord"},
         {"value": "slack",    "label": "Slack"},
     ], "required": True, "default": "telegram"},
    {"name": "message",     "label": "Message text",              "type": "text", "placeholder": "Hello!", "required": True},
    {"name": "chat_id",     "label": "Telegram chat_id (or @username)", "type": "text", "placeholder": "-1001234567890", "required": False},
    {"name": "webhook_url", "label": "Discord/Slack webhook URL (overrides env var)", "type": "text", "placeholder": "https://discord.com/api/webhooks/...", "required": False},
    {"name": "title",       "label": "Embed title (Discord/Slack)", "type": "text", "placeholder": "Notification", "required": False},
]


def _send_telegram(message: str, chat_id: str) -> dict:
    """Send via Telegram Bot API. Needs TELEGRAM_BOT_TOKEN env var."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        return {"error": "TELEGRAM_BOT_TOKEN not set in environment variables."}

    target = chat_id.strip() if chat_id and chat_id.strip() else os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not target:
        return {"error": "No Telegram chat_id provided and TELEGRAM_CHAT_ID not set."}

    try:
        import requests
        url  = f"https://api.telegram.org/bot{token}/sendMessage"
        resp = requests.post(url, json={
            "chat_id":    target,
            "text":       message,
            "parse_mode": "Markdown",
        }, timeout=10)
        data = resp.json()
        if data.get("ok"):
            msg_id = data.get("result", {}).get("message_id", "?")
            return {"result": f"✅ Telegram message sent to {target} (message_id: {msg_id})"}
        return {"error": f"Telegram API error: {data.get('description', data)}"}
    except ImportError:
        return {"error": "requests not installed."}
    except Exception as e:
        return {"error": f"Telegram send failed: {e}"}


def _send_discord(message: str, webhook_url: str, title: str = "") -> dict:
    """Send via Discord webhook. Needs DISCORD_WEBHOOK_URL env var if webhook_url not given."""
    url = webhook_url.strip() if webhook_url and webhook_url.strip() else os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    if not url:
        return {"error": "No Discord webhook URL provided and DISCORD_WEBHOOK_URL not set."}

    try:
        import requests
        payload = {}
        if title:
            payload["embeds"] = [{"title": title, "description": message, "color": 5763719}]
        else:
            payload["content"] = message

        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code in (200, 204):
            return {"result": "✅ Discord message sent successfully."}
        return {"error": f"Discord webhook returned HTTP {resp.status_code}: {resp.text[:200]}"}
    except ImportError:
        return {"error": "requests not installed."}
    except Exception as e:
        return {"error": f"Discord send failed: {e}"}


def _send_slack(message: str, webhook_url: str, title: str = "") -> dict:
    """Send via Slack incoming webhook. Needs SLACK_WEBHOOK_URL env var if webhook_url not given."""
    url = webhook_url.strip() if webhook_url and webhook_url.strip() else os.getenv("SLACK_WEBHOOK_URL", "").strip()
    if not url:
        return {"error": "No Slack webhook URL provided and SLACK_WEBHOOK_URL not set."}

    try:
        import requests
        text    = f"*{title}*\n{message}" if title else message
        payload = {"text": text}
        resp    = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200 and resp.text == "ok":
            return {"result": "✅ Slack message sent successfully."}
        return {"error": f"Slack webhook returned: {resp.text[:200]}"}
    except ImportError:
        return {"error": "requests not installed."}
    except Exception as e:
        return {"error": f"Slack send failed: {e}"}


def run(
    platform:    str = "telegram",
    message:     str = "",
    chat_id:     str = "",
    webhook_url: str = "",
    title:       str = "",
    username:    str = "",
) -> dict:
    from services.permission_manager import perms
    if not perms.check("messaging"):
        return perms.deny_message("messaging")

    platform = (platform or "telegram").lower().strip()
    message  = (message  or "").strip()

    if not message:
        return {"error": "Message text is required."}

    log.info("messaging: platform=%s len=%d", platform, len(message))

    if platform == "telegram":
        return _send_telegram(message, chat_id)
    if platform == "discord":
        return _send_discord(message, webhook_url, title)
    if platform == "slack":
        return _send_slack(message, webhook_url, title)

    return {"error": f"Unknown platform: {platform}. Use: telegram, discord, slack"}
