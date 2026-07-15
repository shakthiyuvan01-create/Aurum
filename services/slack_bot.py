"""
services/slack_bot.py -- Slack channel for Aurum.

Slack works via an inbound events webhook (not a persistent connection), so
this is a route rather than a background loop. Set SLACK_BOT_TOKEN (xoxb-...)
for replies and configure Slack's Event Subscriptions to POST to
/slack/events. SLACK_SIGNING_SECRET verifies requests when set.
"""
import os
import logging

log = logging.getLogger("services.slack_bot")


def answer(text, username="default"):
    from providers import AI
    from services.memory_api import memory
    ctx = memory.context(username, text)
    sysp = "You are AI Aurum on Slack. Be concise." + ("\n\n" + ctx if ctx else "")
    return AI.generate(text, system=sysp, max_tokens=900)[:2900]


def send(channel, text):
    token = os.getenv("SLACK_BOT_TOKEN", "")
    if not token:
        return
    try:
        import requests
        requests.post("https://slack.com/api/chat.postMessage",
                      headers={"Authorization": "Bearer " + token},
                      json={"channel": channel, "text": text}, timeout=20)
    except Exception as e:
        log.warning("slack send failed: %s", e)
