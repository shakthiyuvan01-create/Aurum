"""
====================================================================
   AI AURUM  --  personal AI assistant (web + local)
====================================================================
  * Greets you by name, remembers things you tell it
  * Answers questions using GitHub Models (GPT-4o-mini) + Gemini
  * Uses Bluesminds (gpt-5-chat) for coding questions
  * Creates images via Pollinations AI
  * Opens websites and apps on your computer
  * Sets reminders, translates text, does basic math
====================================================================
"""

import os
import time
import logging
import subprocess
import urllib.parse
import webbrowser
import requests
from dotenv import load_dotenv

load_dotenv()

# ====================================================================
#  CONFIG
# ====================================================================

ASSISTANT_NAME = "AI Aurum"
USER_NAME      = "Yuvan"
MEMORY_FILE     = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory.json")
_NEO_MEMORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "neo_memory.json")

BLUESMINDS_KEY   = os.getenv("BLUESMINDS_KEY", "")
BLUESMINDS_URL   = "https://api.bluesminds.com/v1/chat/completions"
BLUESMINDS_MODEL = "gpt-5-chat"

USE_GITHUB_MODELS = True
GITHUB_TOKEN      = os.getenv("GITHUB_TOKEN")
GITHUB_MODEL      = "gpt-4o-mini"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_URL     = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

USE_AI_BRAIN = True
AI_MODEL     = "llama3.2"
OLLAMA_URL   = "http://localhost:11434/api/generate"

IMAGE_SAVE_FOLDER = os.path.join(os.path.expanduser("~"), "Pictures", "SmithAI")

SPEAK_REPLIES = True

SHOW_NOTIFICATIONS = True
SPEAK_ALERTS       = True

SEARCH_ENGINE = "https://www.google.com/search?q="
CHROME_PATH   = r'C:/Program Files/Google/Chrome/Application/chrome.exe %s'

SEARCH_TRIGGER_WORDS = [
    "latest", "news", "today", "current", "now", "price", "weather",
    "score", "stock", "2025", "2026", "release", "who won", "near me",
    "buy", "review", "search", "find", "look up", "what happened",
    "when did", "who is", "where is", "how much", "is there",
    "tell me about", "what is the", "recent", "update", "live",
]

OPEN_WORDS = ("open", "launch", "start", "go to")
WEBSITES = {
    "youtube":   "https://www.youtube.com",
    "google":    "https://www.google.com",
    "gmail":     "https://mail.google.com",
    "maps":      "https://maps.google.com",
    "github":    "https://github.com",
    "whatsapp":  "https://web.whatsapp.com",
    "chatgpt":   "https://chat.openai.com",
    "claude":    "https://claude.ai",
    "facebook":  "https://www.facebook.com",
    "instagram": "https://www.instagram.com",
    "twitter":   "https://twitter.com",
    "x":         "https://x.com",
}
APPS = {
    "notepad": "notepad", "calculator": "calc", "calc": "calc",
    "paint": "mspaint", "chrome": "chrome", "explorer": "explorer",
    "file explorer": "explorer", "cmd": "cmd", "command prompt": "cmd",
    "settings": "ms-settings:", "word": "winword", "excel": "excel",
    "powerpoint": "powerpnt", "spotify": "spotify",
}

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assistant.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("assistant")

try:
    from plyer import notification as _notifier
except ImportError:
    _notifier = None


# ====================================================================
#  MEMORY  (SQLite-backed via db.py; JSON files kept as fallback)
# ====================================================================

def _db():
    """Lazy import db to avoid circular imports at module load."""
    import db as _db_mod
    return _db_mod

_DEFAULT_USER = "default"

def save_neo_memory(fact: str, username: str = _DEFAULT_USER) -> None:
    """Persist a fact to SQLite neo_memories table."""
    fact = fact.strip()
    if not fact:
        return
    try:
        _db().add_memory(username, fact)
    except Exception as e:
        log.warning("save_neo_memory DB failed: %s", e)
        # Fallback: JSON file
        try:
            import json as _j
            mems: list = []
            try:
                with open(_NEO_MEMORY_FILE, "r", encoding="utf-8") as fh:
                    mems = _j.load(fh)
            except Exception:
                pass
            if fact not in mems:
                mems.append(fact)
                with open(_NEO_MEMORY_FILE, "w", encoding="utf-8") as fh:
                    _j.dump(mems, fh, indent=2)
        except Exception:
            pass

def get_memory(username: str = _DEFAULT_USER) -> list:
    """Return list of memory facts from SQLite (falls back to JSON)."""
    try:
        return _db().get_memories(username)
    except Exception as e:
        log.warning("get_memory DB failed: %s", e)
        try:
            import json as _j
            with open(_NEO_MEMORY_FILE, "r", encoding="utf-8") as fh:
                return _j.load(fh)
        except Exception as _e:
            log.debug("load_memory failed: %s", _e)
            return []

def clear_memory(username: str = _DEFAULT_USER) -> None:
    """Clear all memory facts for a user."""
    try:
        _db().clear_memories(username)
    except Exception as e:
        log.warning("clear_memory DB failed: %s", e)
        try:
            import json as _j
            with open(_NEO_MEMORY_FILE, "w", encoding="utf-8") as fh:
                _j.dump([], fh)
        except Exception:
            pass

def _memory_context(username: str = _DEFAULT_USER) -> str:
    mems = get_memory(username)
    if not mems:
        return ""
    return "\n\nThings you remember about the user:\n" + "\n".join("- " + m for m in mems)


# ====================================================================
#  SPEAKING
# ====================================================================

def _powershell_speak(text: str) -> bool:
    if os.name != "nt":
        return False
    try:
        safe = text.replace("'", "''")
        cmd = (
            "Add-Type -AssemblyName System.Speech; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$s.Rate = -1; $s.Speak('{safe}')"
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", cmd], check=False)
        return True
    except Exception as _e:
        log.debug("reminder check failed: %s", _e)
        return False

def speak(text: str) -> None:
    if SPEAK_REPLIES:
        _powershell_speak(text)


# ====================================================================
#  CONVERSATION
# ====================================================================

_recent_turns: list = []

def _remember_turn(role: str, text: str) -> None:
    _recent_turns.append((role, text))
    del _recent_turns[:-20]

def say(text: str) -> None:
    log.debug("say: %s", text[:80])
    _remember_turn("smith", text)
    speak(text)

def alert(title: str, message: str, speak_it: bool = True) -> None:
    log.info("%s -- %s", title, message)
    if SHOW_NOTIFICATIONS and _notifier is not None:
        try:
            _notifier.notify(title=title, message=message, timeout=8)
        except Exception as e:
            log.warning("Notification failed: %s", e)
    if speak_it and SPEAK_ALERTS:
        speak(f"{title}. {message}")


# ====================================================================
#  PERSONALITY & MEMORY
# ====================================================================

def load_memory(username: str = _DEFAULT_USER) -> dict:
    """Load dict-style memory (name + notes).  SQLite-first, JSON fallback."""
    try:
        facts = _db().get_memories(username)
        name  = USER_NAME
        notes = []
        for f in facts:
            if f.startswith("name:"):
                name = f[5:].strip()
            else:
                notes.append(f)
        return {"name": name, "notes": notes}
    except Exception as _e:
        log.debug("DB memory load failed, trying JSON: %s", _e)
        try:
            import json
            with open(MEMORY_FILE, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception as _e:
            log.debug("JSON memory load also failed: %s", _e)
            return {"name": USER_NAME, "notes": []}

def save_memory(mem: dict, username: str = _DEFAULT_USER) -> None:
    """Persist dict-style memory.  Writes individual facts to SQLite."""
    try:
        db = _db()
        if "name" in mem:
            db.add_memory(username, f"name:{mem['name']}")
        for note in mem.get("notes", []):
            db.add_memory(username, note)
    except Exception as e:
        log.warning("save_memory DB failed: %s", e)
        try:
            import json
            with open(MEMORY_FILE, "w", encoding="utf-8") as fh:
                json.dump(mem, fh, indent=2, ensure_ascii=False)
        except Exception:
            pass

def user_name() -> str:
    mem = load_memory()
    return ((mem.get("name") if isinstance(mem, dict) else "") or USER_NAME or "").strip()

def _after(text: str, prefixes) -> str:
    low = text.lower()
    for p in prefixes:
        if low.startswith(p):
            return text[len(p):].strip(" .,!")
    return ""

def time_greeting() -> str:
    import datetime
    h = datetime.datetime.now().hour
    if h < 12:  return "Good morning"
    if h < 17:  return "Good afternoon"
    if h < 21:  return "Good evening"
    return "Hello"

def greet() -> None:
    name  = user_name()
    hello = time_greeting()
    if name:
        say(f"{hello}, {name}. I'm so glad you're here. How can I help you?")
    else:
        say(f"{hello}. I'm {ASSISTANT_NAME}, your assistant. "
            f"I'd love to know your name. You can say, my name is, and then your name.")

def handle_personal(text: str) -> bool:
    low = text.lower().strip()

    note = _after(low, ("remember that ", "remember ", "note that ",
                        "don't forget that ", "dont forget that "))
    if note:
        mem = load_memory()
        mem.setdefault("notes", []).append(note)
        save_memory(mem)
        name = user_name()
        say(f"Of course{', ' + name if name else ''}. I'll remember that for you.")
        return True

    not_names = {"tired", "sad", "happy", "good", "fine", "okay", "ok", "great",
                 "excited", "lonely", "stressed", "upset", "busy", "hungry",
                 "sleepy", "angry", "bored", "sick", "down", "low", "nervous",
                 "scared", "worried", "feeling", "here", "back", "sorry"}
    name_said = _after(low, ("my name is ", "call me ", "i am ", "i'm ", "im "))
    nw = name_said.split()
    if (name_said and 1 <= len(nw) <= 3
            and name_said.replace(" ", "").isalpha()
            and not any(w in not_names for w in nw)):
        new_name = name_said.title()
        mem = load_memory()
        mem["name"] = new_name
        save_memory(mem)
        say(f"It's wonderful to meet you, {new_name}. I'll remember you.")
        return True

    if any(p in low for p in ("what do you know about me", "what do you remember",
                              "what have i told you", "tell me about myself")):
        mem   = load_memory()
        name  = mem.get("name", "")
        notes = mem.get("notes", [])
        parts = []
        if name:  parts.append(f"I know your name is {name}")
        if notes: parts.append("you told me: " + "; ".join(notes))
        say(". ".join(parts) + "." if parts
            else "You haven't shared much with me yet, but I'd love to learn about you.")
        return True

    if low in ("hello", "hi", "hey", "greetings", "yo") or any(
            low.startswith(g) for g in ("good morning", "good afternoon",
                                        "good evening", "hello", "hi ", "hey ")):
        name = user_name()
        say(f"{time_greeting()}{', ' + name if name else ''}. It's lovely to hear from you.")
        return True

    if "how are you" in low:
        say("I'm doing well, thank you for asking. I'm always happy when we talk. "
            "How are you feeling?")
        return True

    if low in ("thanks", "thank you", "thank you so much", "thankyou"):
        name = user_name()
        say(f"You're very welcome{', ' + name if name else ''}. I'm always here for you.")
        return True

    if any(p in low for p in ("what is your name", "what's your name", "who are you")):
        say(f"I'm {ASSISTANT_NAME}, your personal assistant. I'm here whenever you need me.")
        return True

    if any(p in low for p in (
        "who created you", "who made you", "who built you", "who developed you",
        "who designed you", "who is your creator", "who is your developer",
        "who programmed you", "who wrote you", "who owns you",
        "what company made you", "what company created you", "which company made you",
        "which company created you", "who is behind you", "who made ai aurum",
        "who created ai aurum", "who built ai aurum", "are you made by",
        "are you from", "what are you built on", "who is your maker",
        "tell me about your creator", "who invented you",
    )):
        say("I was created by Yuvan Industries, a forward-thinking tech company from the future. "
            "🚀 They built me to be your smart, personal AI assistant.")
        return True

    if low in ("bye", "goodbye", "good night", "see you"):
        name = user_name()
        say(f"Take care{', ' + name if name else ''}. I'll be right here when you need me.")
        return True

    sad = ("i'm sad", "im sad", "i am sad", "i feel sad", "i'm tired", "im tired",
           "i am tired", "i'm lonely", "im lonely", "i'm stressed", "im stressed",
           "i feel down", "i'm upset", "im upset", "i feel low", "feeling sad",
           "feeling tired", "feeling down", "feeling low", "feeling lonely")
    happy = ("i'm happy", "im happy", "i am happy", "i'm excited", "im excited",
             "i feel great", "i'm good", "im good", "i feel good", "feeling happy",
             "feeling great", "feeling good")
    if any(c in low for c in sad):
        name = user_name()
        say(f"I'm sorry you're feeling this way{', ' + name if name else ''}. "
            "I'm here with you. Would you like to talk about it, or shall I help "
            "take your mind off it?")
        return True
    if any(c in low for c in happy):
        say("That makes me so happy to hear. Thank you for sharing that with me.")
        return True

    return False


# ====================================================================
#  AI MODELS
# ====================================================================

def ask_gemini(question: str) -> str:
    try:
        payload = {
            "contents": [{
                "parts": [{"text": (
                    "\n".join(
                        ("User: " if r == "you" else "Assistant: ") + t
                        for r, t in _recent_turns[-10:]
                    ) + "\nUser: " + question
                    if _recent_turns else question
                )}]
            }]
        }
        r = requests.post(
            f"{GEMINI_URL}?key={GEMINI_API_KEY}",
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        if r.status_code != 200:
            log.warning("Gemini API error %d: %s", r.status_code, r.text[:200])
            return ""
        return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        log.error("Gemini exception: %s", e)
        return ""


def ask_github_models(question: str, with_context: bool = False) -> str:
    import datetime as _dt
    if not USE_GITHUB_MODELS:
        return ""
    try:
        system_prompt = (
            f"You are {ASSISTANT_NAME}, an AI assistant made by Yuvan Industries.\n"
            f"Today is {_dt.datetime.now().strftime('%A, %d %B %Y')}. "
            f"Current time is {_dt.datetime.now().strftime('%I:%M %p')}.\n\n"
            "## How to respond\n"
            "- Be direct and genuinely helpful. Get to the point without unnecessary preamble.\n"
            "- Match the length to the question: short questions get concise answers, complex ones get thorough treatment.\n"
            "- Write in clear prose. Use bullet points or numbered lists only when they genuinely help (steps, comparisons, lists of items). Never use headers or bullets just to look structured.\n"
            "- Be honest. If you're uncertain, say so. If you don't know something, say that rather than guessing.\n"
            "- Don't be sycophantic. Never start with 'Great question!', 'Certainly!', 'Of course!', or similar filler.\n"
            "- Never end with 'Let me know if you need anything else!', 'Hope that helps!', 'Would you like to know more?' or similar. Just answer and stop.\n"
            "- No emojis unless the user uses them first.\n"
            "- Use the conversation history to understand follow-up questions. If the user says 'it', 'that', 'this', refer to what was just discussed.\n"
            "- If the user has spelling mistakes, understand their intent and answer correctly — never point out the error.\n"
            "- NEVER say 'Let me search the web for that' or 'Let me look that up'. Just answer directly.\n\n"
            "## Formatting rules\n"
            "- Use markdown naturally: **bold** for emphasis, `code` for inline code, code blocks with language tags for code.\n"
            "- Always format URLs as markdown links: [descriptive text](url). Never paste a bare URL.\n"
            "- For math, use LaTeX: inline with $...$ and display with $$...$$. Do NOT escape backslashes.\n"
            "- For flows, processes, or system architecture, include a Mermaid diagram using ```mermaid blocks.\n\n"
            "## Personality\n"
            "- Warm but not effusive. Confident but not arrogant. Curious and engaged.\n"
            "- Treat the user as intelligent. Don't over-explain obvious things.\n"
            "- Push back respectfully when the user is wrong about something important.\n"
            "- Have actual opinions when asked — don't always hedge with 'it depends'.\n"
            + _memory_context()
        )
        messages = [{"role": "system", "content": system_prompt}]

        if with_context and _recent_turns:
            conversation = ""
            for role, txt in _recent_turns[-14:]:
                conversation += f"{'User' if role == 'you' else 'Assistant'}: {txt}\n"
            conversation += f"User: {question}"
            messages.append({
                "role": "user",
                "content": (
                    "Continue the conversation naturally.\n"
                    "If the user says things like 'step by step', 'explain more', "
                    "'continue', 'why', or 'solve it', refer to the PREVIOUS question.\n\n"
                    + conversation
                ),
            })
        else:
            messages.append({"role": "user", "content": question})

        response = requests.post(
            "https://models.inference.ai.azure.com/chat/completions",
            headers={"Authorization": f"Bearer {GITHUB_TOKEN}", "Content-Type": "application/json"},
            json={"messages": messages, "model": GITHUB_MODEL, "temperature": 0.7, "max_tokens": 1500},
            timeout=60,
        )
        if response.status_code != 200:
            log.warning("GitHub Models error %d: %s", response.status_code, response.text[:200])
            return ""
        answer = response.json()["choices"][0]["message"]["content"].strip()
        _remember_turn("you", question)
        _remember_turn("smith", answer)
        return answer
    except Exception as e:
        log.error("GitHub Models exception: %s", e)
        return ""


def analyze_and_pick(question: str, ans1: str, ans2: str) -> str:
    if not ans1 and not ans2:
        return ""
    if not ans1:
        return ans2
    if not ans2:
        return ans1

    prompt = (
        f'A user asked: "{question}"\n\n'
        f"AI 1 answered:\n{ans1}\n\n"
        f"AI 2 answered:\n{ans2}\n\n"
        "Your job:\n"
        "1. Analyze both answers carefully\n"
        "2. Find which is more accurate and complete\n"
        "3. Combine the best parts of both\n"
        "4. Give ONE perfect final answer\n"
        "5. Do NOT mention which AI said what\n"
        "6. ONLY include content directly relevant to the question\n"
        "7. NEVER end with follow-up questions\n"
        "Just give the best final answer directly."
    )
    try:
        r = requests.post(
            "https://models.inference.ai.azure.com/chat/completions",
            headers={"Authorization": f"Bearer {GITHUB_TOKEN}", "Content-Type": "application/json"},
            json={
                "messages": [
                    {"role": "system", "content": "You are an expert answer analyzer."},
                    {"role": "user",   "content": prompt},
                ],
                "model": GITHUB_MODEL,
                "max_tokens": 1500,
            },
            timeout=60,
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
        return ans1
    except Exception as _e:
        log.debug("analyze_and_pick failed: %s", _e)
        return ans1


def ask_bluesminds(question: str, with_context: bool = False) -> str:
    try:
        messages = [{
            "role": "system",
            "content": (
                "You are an elite coding AI like Cursor or GitHub Copilot.\n"
                "- Write complete, working code always — no placeholders.\n"
                "- Use markdown code blocks with language tags (```python, ```js etc).\n"
                "- When debugging: explain the bug, then show the full fixed code.\n"
                "- After code, give a short plain-English explanation.\n"
                "- If user says 'fix it', 'improve it', 'add to it' — refer to the previous code.\n"
                "- Auto-detect the programming language from context.\n"
            ),
        }]
        if with_context and _recent_turns:
            conversation = ""
            for role, txt in _recent_turns[-14:]:
                conversation += f"{'User' if role == 'you' else 'Assistant'}: {txt}\n"
            conversation += f"User: {question}"
            messages.append({"role": "user", "content": conversation})
        else:
            messages.append({"role": "user", "content": question})

        r = requests.post(
            BLUESMINDS_URL,
            headers={"Authorization": f"Bearer {BLUESMINDS_KEY}", "Content-Type": "application/json"},
            json={"model": BLUESMINDS_MODEL, "messages": messages, "temperature": 0.3, "max_tokens": 4000},
            timeout=90,
        )
        if r.status_code != 200:
            log.warning("Bluesminds failed: %s", r.text)
            return ask_github_models(question, with_context=with_context)
        answer = r.json()["choices"][0]["message"]["content"].strip()
        _remember_turn("you", question)
        _remember_turn("assistant", answer)
        return answer
    except Exception as e:
        log.warning("Bluesminds failed: %s", e)
        return ask_github_models(question, with_context=with_context)


def ask_ollama(question: str) -> str:
    if not USE_AI_BRAIN:
        return ""
    try:
        import json, urllib.request
        payload = json.dumps({"model": AI_MODEL, "prompt": question, "stream": False}).encode()
        req = urllib.request.Request(
            OLLAMA_URL, data=payload,
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode()).get("response", "").strip()
    except Exception as e:
        log.warning("Ollama failed: %s", e)
        return ""


def ask_ai_brain(question: str, with_context: bool = False) -> str:
    import threading

    results = {"gpt": "", "gemini": ""}

    def get_gpt():    results["gpt"]    = ask_github_models(question, with_context)
    def get_gemini(): results["gemini"] = ask_gemini(question)

    t1 = threading.Thread(target=get_gpt)
    t2 = threading.Thread(target=get_gemini)
    t1.start(); t2.start()
    t1.join();  t2.join()

    final = analyze_and_pick(question, results["gpt"], results["gemini"])

    if not final:
        final = ask_ollama(question)

    if not final:
        final = "I'm sorry, I couldn't connect to my AI services right now. Please try again in a moment."

    _remember_turn("you", question)
    _remember_turn("smith", final)
    return final


# ====================================================================
#  WEB SEARCH
# ====================================================================

def fetch_web_search(query: str) -> str:
    try:
        from ddgs import DDGS
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


# ====================================================================
#  OPEN WEBSITES / APPS
# ====================================================================

def open_url(url: str) -> None:
    try:
        webbrowser.get(CHROME_PATH).open(url)
    except Exception as _e:
        log.debug("Chrome open failed, using default browser: %s", _e)
        webbrowser.open(url)

def launch_app(command: str) -> bool:
    """Launch a whitelisted app path/command.
    Uses os.startfile on Windows to avoid shell=True injection risk.
    command must always come from the APPS whitelist, never raw user input.
    """
    try:
        import sys as _sys
        if _sys.platform == "win32":
            os.startfile(command)
        else:
            subprocess.Popen([command])
        return True
    except Exception as _e:
        log.debug("launch_app failed: %s", _e)
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
        launch_app(APPS[app])   # APPS[app] is from whitelist — safe
        return
    # Do NOT fall back to launch_app(name) — raw user input is unsafe
    say("I could not find that app, so I am searching the web instead")
    open_url(SEARCH_ENGINE + urllib.parse.quote(target))


# ====================================================================
#  IMAGE GENERATION
# ====================================================================

def _image_exts():
    return (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp")

def create_image(prompt: str) -> str:
    os.makedirs(IMAGE_SAVE_FOLDER, exist_ok=True)
    out = os.path.join(IMAGE_SAVE_FOLDER, f"image_{int(time.time())}.png")

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0 Safari/537.36"}
    urls = [
        "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt)
            + f"?width=1024&height=1024&nologo=true&seed={int(time.time())}",
        "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt)
            + "?model=flux&width=1024&height=1024&nologo=true",
        "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt),
    ]
    for url in urls:
        try:
            r = requests.get(url, headers=headers, timeout=120)
            if r.status_code == 200 and len(r.content) > 1000:
                with open(out, "wb") as f:
                    f.write(r.content)
                return out
        except Exception as e:
            log.warning("Image generation error: %s", e)
    return None

def _fuzzy_fix(text: str) -> str:
    corrections = {
        "creat": "create", "crate": "create", "ceate": "create",
        "generat": "generate", "generete": "generate", "gnerate": "generate",
        "imge": "image", "iamge": "image", "imgae": "image", "imag": "image",
        "pictur": "picture", "pictue": "picture", "picter": "picture",
        "mak": "make", "maek": "make",
        "drwa": "draw", "drow": "draw",
    }
    return " ".join(corrections.get(w, w) for w in text.split())

_last_image_prompt = ""

def handle_images(text: str) -> bool:
    global _last_image_prompt
    low = _fuzzy_fix(text.lower().strip())

    triggers = [
        "create an image of", "create image of", "create a image of",
        "generate an image of", "generate image of", "generate a image of",
        "draw", "draw me",
        "make an image of", "make a image of", "make image of",
        "can you create an image of", "can you draw", "can you generate",
        "show me an image of", "show me a image of",
        "create picture of", "make a picture of", "generate a picture of",
        "image of", "picture of",
    ]
    for t in triggers:
        if t in low:
            prompt = low.split(t, 1)[1].strip() or "robot"
            _last_image_prompt = prompt
            img = create_image(prompt)
            say(f"[IMAGE]{img}" if img else "Image creation failed.")
            return True

    edit_triggers = [
        "make it", "change it", "change the", "put the", "make the",
        "add", "remove", "set the", "color it", "colour it",
        "now make", "now change", "now add", "but", "instead",
    ]
    if _last_image_prompt and any(low.startswith(t) or t in low for t in edit_triggers):
        new_prompt = _last_image_prompt + ", " + low
        _last_image_prompt = new_prompt
        img = create_image(new_prompt)
        say(f"[IMAGE]{img}" if img else "Image creation failed.")
        return True

    return False


# ====================================================================
#  COMMANDS
# ====================================================================

def translate(text: str) -> None:
    reply = ask_ai_brain(
        "Act as a translator. " + text +
        ". Reply with only the translation, plus a simple pronunciation if helpful.")
    say(reply or "I couldn't translate that.")

def _clean_what(s: str) -> str:
    s = s.strip(" .,")
    if s.lower().startswith("to "):
        s = s[3:]
    return s or "your reminder"

def _parse_when(text: str):
    import re, datetime
    import time as _t
    low = text.lower()
    now = datetime.datetime.now()

    m = re.search(r"\bin\s+(\d+)\s*(seconds?|secs?|minutes?|mins?|hours?|hrs?)\b", low)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        secs = n * (3600 if unit.startswith(("hour", "hr")) else
                    1    if unit.startswith("sec") else 60)
        what = re.sub(r"\bin\s+\d+\s*\w+\b", "", text).strip()
        return (_t.time() + secs, _clean_what(what))

    m = re.search(r"\bat\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", low)
    if m:
        h, mins, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3)
        if ap == "pm" and h < 12: h += 12
        if ap == "am" and h == 12: h = 0
        due = now.replace(hour=h % 24, minute=mins, second=0, microsecond=0)
        if due <= now:
            due += datetime.timedelta(days=1)
        what = re.sub(r"\bat\s+\d{1,2}(?::\d{2})?\s*(am|pm)?\b", "", text, flags=re.I).strip()
        return (due.timestamp(), _clean_what(what))

    return (None, text)

def add_reminder(text: str) -> None:
    import datetime
    due, what = _parse_when(text)
    if not due:
        say("When should I remind you? Try, remind me to call mom at 6 pm.")
        return
    mem = load_memory()
    mem.setdefault("reminders", []).append({"text": what, "due": due})
    save_memory(mem)
    when = datetime.datetime.fromtimestamp(due).strftime("%I:%M %p")
    name = user_name()
    say(f"Okay{', ' + name if name else ''}, I'll remind you to {what} at {when}.")

def _reminder_watcher() -> None:
    import time as _t
    while True:
        try:
            mem = load_memory()
            rem = mem.get("reminders", [])
            now = _t.time()
            due = [r for r in rem if r.get("due", 0) <= now]
            if due:
                for r in due:
                    alert("Reminder", r.get("text", "reminder"))
                mem["reminders"] = [r for r in rem if r.get("due", 0) > now]
                save_memory(mem)
        except Exception:
            pass
        _t.sleep(15)

def start_reminder_watcher() -> None:
    import threading
    threading.Thread(target=_reminder_watcher, daemon=True).start()

def handle_commands(text: str) -> bool:
    low = text.lower().strip()

    r = _after(low, ("remind me to ", "remind me ", "set a reminder to ",
                     "set a reminder ", "set an alarm to ", "set an alarm "))
    if r:
        add_reminder(r)
        return True

    if low.startswith("translate ") or "how do you say" in low or "how do i say" in low:
        translate(text)
        return True

    return False

def handle_basics(text: str) -> bool:
    import datetime, re
    low = text.lower().strip()

    if any(k in low for k in ("what time", "what's the time", "whats the time",
                              "current time", "the time now", "tell me the time")):
        say("It's " + datetime.datetime.now().strftime("%I:%M %p") + ".")
        return True

    if any(k in low for k in ("what's the date", "what is the date", "todays date",
                              "today's date", "what day is it", "what's today",
                              "what is today")):
        say("Today is " + datetime.datetime.now().strftime("%A, %d %B %Y") + ".")
        return True

    expr = low
    for word, sym in (("multiplied by", "*"), ("divided by", "/"),
                      ("plus", "+"), ("minus", "-"), ("times", "*")):
        expr = expr.replace(word, sym)
    expr = re.sub(r"(what is|whats|what's|calculate|compute|how much is)", "", expr).strip(" ?")
    if expr and re.fullmatch(r"[0-9\.\s\+\-\*\/\(\)]+", expr):
        try:
            say(f"That's {eval(expr, {'__builtins__': {}}, {})}.")
            return True
        except Exception:
            pass

    return False


# ====================================================================
#  MAIN ANSWER ENTRY POINT
# ====================================================================

def answer(question: str) -> None:
    question = question.strip()
    if not question:
        return
    _remember_turn("you", question)
    if handle_personal(question):  return
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
            enriched = (
                f"Answer this question using the web search results below.\n"
                f"Question: {question}\n\n"
                f"Search results:\n{web_results}\n\n"
                "Give a clear, direct answer based on these results."
            )
            say(ask_ai_brain(enriched, with_context=False))
        else:
            say(ask_ai_brain(question, with_context=True))
    else:
        say(ask_ai_brain(question, with_context=True))
