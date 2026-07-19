"""assistant/models.py — AI model wrappers: Gemini, GitHub Models, Bluesminds, Ollama."""
import datetime
import logging
import threading

import requests as _requests

from assistant.config import (
    GITHUB_TOKEN, GITHUB_MODEL, USE_GITHUB_MODELS,
    GEMINI_API_KEY, GEMINI_URL,
    BLUESMINDS_KEY, BLUESMINDS_URL, BLUESMINDS_MODEL,
    USE_AI_BRAIN, AI_MODEL, OLLAMA_URL,
    ASSISTANT_NAME,
)
from assistant.memory import _memory_context, get_memory

log = logging.getLogger("assistant.models")

# Short-term conversation ring buffer (shared mutable state)
_recent_turns: list = []
_MAX_TURNS = 20


def _remember_turn(role: str, text: str) -> None:
    _recent_turns.append((role, text))
    if len(_recent_turns) > _MAX_TURNS:
        _recent_turns.pop(0)


def ask_gemini(question: str) -> str:
    if not GEMINI_API_KEY:
        return ""
    try:
        payload = {"contents": [{"parts": [{"text": question}]}]}
        r = _requests.post(
            f"{GEMINI_URL}?key={GEMINI_API_KEY}",
            headers={"Content-Type": "application/json"},
            json=payload, timeout=30,
        )
        if r.status_code != 200:
            log.warning("Gemini %d: %s", r.status_code, r.text[:200])
            return ""
        return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        log.error("Gemini: %s", e)
        return ""


def ask_github_models(question: str, with_context: bool = False) -> str:
    if not USE_GITHUB_MODELS or not GITHUB_TOKEN:
        return ""
    try:
        now = datetime.datetime.now()
        system_prompt = (
            f"You are {ASSISTANT_NAME}, an AI assistant made by Yuvan Industries.\n"
            f"Today is {now.strftime('%A, %d %B %Y')}. "
            f"Time: {now.strftime('%I:%M %p')}.\n\n"
            "Be direct and genuinely helpful. Match length to complexity. "
            "No filler, no sycophancy, no trailing questions. "
            "Use markdown: **bold**, `code`, code blocks with language tags, "
            "LaTeX for math ($...$).\n"
            + _memory_context()
        )
        messages = [{"role": "system", "content": system_prompt}]
        if with_context and _recent_turns:
            conv = "\n".join(
                f"{'User' if r == 'you' else 'Assistant'}: {t}"
                for r, t in _recent_turns[-14:]
            ) + f"\nUser: {question}"
            messages.append({"role": "user", "content": conv})
        else:
            messages.append({"role": "user", "content": question})

        r = _requests.post(
            "https://models.inference.ai.azure.com/chat/completions",
            headers={"Authorization": f"Bearer {GITHUB_TOKEN}", "Content-Type": "application/json"},
            json={"messages": messages, "model": GITHUB_MODEL, "temperature": 0.7, "max_tokens": 1500},
            timeout=60,
        )
        if r.status_code != 200:
            log.warning("GitHub Models %d: %s", r.status_code, r.text[:200])
            return ""
        answer = r.json()["choices"][0]["message"]["content"].strip()
        _remember_turn("you", question)
        _remember_turn("smith", answer)
        return answer
    except Exception as e:
        log.error("GitHub Models: %s", e)
        return ""


def analyze_and_pick(question: str, ans1: str, ans2: str) -> str:
    if not ans1 and not ans2: return ""
    if not ans1: return ans2
    if not ans2: return ans1
    prompt = (
        f'User asked: "{question}"\n\nAI 1:\n{ans1}\n\nAI 2:\n{ans2}\n\n'
        "Combine the best parts into ONE perfect final answer. "
        "Do NOT mention which AI said what. Output only the answer."
    )
    try:
        r = _requests.post(
            "https://models.inference.ai.azure.com/chat/completions",
            headers={"Authorization": f"Bearer {GITHUB_TOKEN}", "Content-Type": "application/json"},
            json={"messages": [
                {"role": "system", "content": "You are an expert answer synthesiser."},
                {"role": "user",   "content": prompt},
            ], "model": GITHUB_MODEL, "max_tokens": 1500},
            timeout=60,
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        log.debug("analyze_and_pick: %s", e)
    return ans1


def ask_bluesminds(question: str, with_context: bool = False) -> str:
    if not BLUESMINDS_KEY:
        return ask_github_models(question, with_context)
    try:
        messages = [{"role": "system", "content": (
            "You are an elite coding AI. Write complete, working code always. "
            "Use markdown code blocks with language tags. After code, give a brief explanation."
        )}]
        if with_context and _recent_turns:
            conv = "\n".join(
                f"{'User' if r == 'you' else 'Assistant'}: {t}"
                for r, t in _recent_turns[-14:]
            ) + f"\nUser: {question}"
            messages.append({"role": "user", "content": conv})
        else:
            messages.append({"role": "user", "content": question})

        r = _requests.post(
            BLUESMINDS_URL,
            headers={"Authorization": f"Bearer {BLUESMINDS_KEY}", "Content-Type": "application/json"},
            json={"model": BLUESMINDS_MODEL, "messages": messages, "temperature": 0.3, "max_tokens": 4000},
            timeout=90,
        )
        if r.status_code != 200:
            return ask_github_models(question, with_context)
        answer = r.json()["choices"][0]["message"]["content"].strip()
        _remember_turn("you", question)
        _remember_turn("assistant", answer)
        return answer
    except Exception as e:
        log.warning("Bluesminds: %s", e)
        return ask_github_models(question, with_context)


def ask_ollama(question: str) -> str:
    if not USE_AI_BRAIN:
        return ""
    try:
        import json, urllib.request
        payload = json.dumps({"model": AI_MODEL, "prompt": question, "stream": False}).encode()
        req = urllib.request.Request(OLLAMA_URL, data=payload,
                                      headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode()).get("response", "").strip()
    except Exception as e:
        log.debug("Ollama: %s", e)
        return ""


def ask_ai_brain(question: str, with_context: bool = False) -> str:
    """FAST AI call via the ProviderManager (parallel racing, ~6s timeout).

    Uses the same system prompt and memory context as before but replaces the
    old 65s parallel + 60s analyze_and_pick + 30s Ollama chain with a single
    call to the fast provider manager which races providers in 6 seconds.
    """
    now = datetime.datetime.now()
    system_prompt = (
        f"You are {ASSISTANT_NAME}, an AI assistant made by Yuvan Industries.\n"
        f"Today is {now.strftime('%A, %d %B %Y')}. "
        f"Time: {now.strftime('%I:%M %p')}.\n\n"
        "Be direct and genuinely helpful. Match length to complexity. "
        "No filler, no sycophancy, no trailing questions. "
        "Use markdown: **bold**, `code`, code blocks with language tags, "
        "LaTeX for math ($...$).\n"
        + _memory_context()
    )

    if with_context and _recent_turns:
        conv = "\n".join(
            f"{'User' if r == 'you' else 'Assistant'}: {t}"
            for r, t in _recent_turns[-14:]
        ) + f"\nUser: {question}"
        prompt = conv
    else:
        prompt = question

    try:
        from providers import AI
        final = AI.generate(prompt, system=system_prompt,
                            max_tokens=1500, temperature=0.7)
    except Exception as e:
        log.error("ask_ai_brain failed: %s", e)
        final = ""

    if not final or final.startswith("[AI error"):
        final = "I'm sorry, I couldn't connect to my AI services right now. Please try again."

    _remember_turn("you", question)
    _remember_turn("smith", final)
    return final
