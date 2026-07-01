"""assistant/web.py — Web search, URL/app opener."""
import logging
import subprocess
import urllib.parse
import webbrowser

from assistant.config import (
    SEARCH_ENGINE, CHROME_PATH, SEARCH_TRIGGER_WORDS,
    OPEN_WORDS, WEBSITES, APPS,
)
from assistant.speech import say

log = logging.getLogger("assistant.web")


def fetch_web_search(query: str) -> str:
    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=4))
        if not results:
            return ""
        return "\n".join(f"- {r['title']}: {r['body']}" for r in results)
    except Exception as e:
        log.warning("Web search failed: %s", e)
        return ""


def needs_web(question: str) -> bool:
    low = question.lower()
    return any(t in low for t in SEARCH_TRIGGER_WORDS)


def open_url(url: str) -> None:
    try:
        webbrowser.get(CHROME_PATH).open(url)
    except Exception:
        webbrowser.open(url)


def launch_app(command: str) -> bool:
    """Launch a whitelisted app. command must come from APPS — never raw user input."""
    try:
        import sys
        if sys.platform == "win32":
            import os
            os.startfile(command)
        else:
            subprocess.Popen([command])
        return True
    except Exception as e:
        log.debug("launch_app: %s", e)
        return False


def get_open_target(question: str):
    low = question.lower().strip()
    for word in OPEN_WORDS:
        if low.startswith(word + " "):
            return low[len(word):].strip()
    return None


def do_open(target: str) -> None:
    name    = target.lower().strip()
    nospace = name.replace(" ", "")
    site = name if name in WEBSITES else (nospace if nospace in WEBSITES else None)
    if site:
        say(f"Opening {site}")
        open_url(WEBSITES[site])
        return
    app = name if name in APPS else (nospace if nospace in APPS else None)
    if app:
        say(f"Opening {app}")
        launch_app(APPS[app])
        return
    say("I couldn't find that app, so I'm searching the web instead.")
    open_url(SEARCH_ENGINE + urllib.parse.quote(target))
