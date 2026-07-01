"""assistant/router.py — Main answer() entry point."""
import logging

from assistant.commands import handle_personal, handle_commands, handle_basics
from assistant.image    import handle_images
from assistant.models   import ask_ai_brain, _remember_turn
from assistant.speech   import say
from assistant.web      import fetch_web_search, needs_web, get_open_target, do_open

log = logging.getLogger("assistant.router")


def answer(question: str) -> None:
    question = question.strip()
    if not question:
        return
    _remember_turn("you", question)
    if handle_personal(question): return
    if handle_commands(question):  return
    if handle_basics(question):    return
    if handle_images(question):    return
    target = get_open_target(question)
    if target:
        do_open(target)
        return
    if needs_web(question):
        web_results = fetch_web_search(question)
        if web_results:
            say(ask_ai_brain(question + "\n\nWeb search results:\n" + web_results))
        else:
            say(ask_ai_brain(question))
        return
    say(ask_ai_brain(question))
