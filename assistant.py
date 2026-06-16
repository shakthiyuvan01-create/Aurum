"""
====================================================================
   PERSONAL ASSISTANT  --  one file, runs on your own machine
====================================================================
Everything in one program:

  * Watches a folder, your system health, your EMAIL, and what you're
    doing (active window) -- and tells you about it.
  * You can ASK it things (type or speak). It opens apps/websites,
    answers simple questions with a local AI, or searches Chrome.
  * It SPEAKS softly, GREETS you, and REMEMBERS personal things.
  * Can AUTO-START with Windows.

No paid API. The optional AI brain uses Ollama (free, local).

--------------------------------------------------------------------
HOW TO RUN
--------------------------------------------------------------------
  python assistant.py             -> background mode (watches & alerts)
  python assistant.py --chat      -> type to it
  python assistant.py --voice     -> talk to it (needs the Vosk model)
  python assistant.py --install   -> start automatically with Windows
  python assistant.py --uninstall -> stop starting automatically

You can also ask one thing:
  python assistant.py "open youtube"
--------------------------------------------------------------------
"""

import os
import sys
import time
import logging
import subprocess
import urllib.parse
import webbrowser

# ====================================================================
#  CONFIG  --  change these to suit you
# ====================================================================
import requests
import os

from dotenv import load_dotenv

load_dotenv()
# ---- Personality & memory ----------------------------------------
ASSISTANT_NAME = "Assist Neo"     # what your assistant is called
BLUESMINDS_KEY = os.getenv("BLUESMINDS_KEY", "")
BLUESMINDS_URL = "https://api.bluesminds.com/v1/chat/completions"
BLUESMINDS_MODEL = "gpt-5-chat"
USER_NAME = "Yuvan"           # it will address you by this name
MEMORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory.json")
_NEO_MEMORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "neo_memory.json")

def _load_memory():
    try:
        with open(_NEO_MEMORY_FILE, "r", encoding="utf-8") as f:
            import json as _j; return _j.load(f)
    except:
        return []

def save_memory(fact):
    import json as _j
    mems = _load_memory()
    if fact.strip() and fact.strip() not in mems:
        mems.append(fact.strip())
        with open(_NEO_MEMORY_FILE, "w", encoding="utf-8") as f:
            _j.dump(mems, f, indent=2)

def get_memory():
    return _load_memory()

def clear_memory():
    import json as _j
    with open(_NEO_MEMORY_FILE, "w", encoding="utf-8") as f:
        _j.dump([], f)

def _memory_context():
    mems = _load_memory()
    if not mems:
        return ""
    return "\n\nThings you remember about the user:\n" + "\n".join("- " + m for m in mems)
# ---- Soft, gentle voice -------------------------------------------
SPEAK_REPLIES = True   # speak answers out loud
SPEAK_ALERTS = True    # speak background alerts (email, activity, etc.)
SPEAK_SPEED = 150      # words per minute (lower = softer)
SPEAK_VOLUME = 0.9     # 0.0 to 1.0
SOFT_VOICE = True      # prefer a gentler voice if installed

# ---- Folder watching ----------------------------------------------
WATCH_FOLDER_ENABLED = True
WATCH_FOLDER = os.path.join(os.path.expanduser("~"), "Downloads")

# ---- System health watching --------------------------------------
WATCH_SYSTEM_ENABLED = True
CPU_LIMIT_PERCENT = 90
RAM_LIMIT_PERCENT = 90
DISK_LIMIT_PERCENT = 90
SYSTEM_CHECK_SECONDS = 10

# ---- EMAIL reading (IMAP) -----------------------------------------
# SECURITY: fill these in on YOUR computer only. Use an APP PASSWORD,
# never your real password. The details stay on your machine.
#   Gmail app password:   https://myaccount.google.com/apppasswords
#   (Outlook/Office365 server is "outlook.office365.com")
EMAIL_ENABLED = False
EMAIL_ADDRESS = "you@example.com"
EMAIL_APP_PASSWORD = ""               # paste your app password here
IMAP_SERVER = "imap.gmail.com"
EMAIL_CHECK_SECONDS = 120

# ---- Activity watching (what you're doing) ------------------------
ACTIVITY_ENABLED = True
ANNOUNCE_ACTIVITY = False   # if True, it speaks each time you switch apps
ACTIVITY_CHECK_SECONDS = 5

# ---- Reactions / desktop notifications ----------------------------
SHOW_NOTIFICATIONS = True
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assistant.log")

# ---- Asking: search vs answer -------------------------------------
BIG_QUESTION_WORDS = 8
SEARCH_TRIGGER_WORDS = [
    "latest", "news", "today", "current", "now", "price", "weather",
    "score", "stock", "2025", "2026", "release", "who won", "near me",
    "buy", "review",
]
SEARCH_ENGINE = "https://www.google.com/search?q="
CHROME_PATH = r'C:/Program Files/Google/Chrome/Application/chrome.exe %s'

# ---- Voice input (offline via Vosk) -------------------------------
VOSK_MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model")
SAMPLE_RATE = 16000
WAKE_WORD = "hey smith"   # say this to wake it in --voice mode ("" = no wake word)

# ---- "open ___" commands ------------------------------------------
OPEN_WORDS = ("open", "launch", "start", "go to")
WEBSITES = {
    "youtube": "https://www.youtube.com", "google": "https://www.google.com",
    "gmail": "https://mail.google.com", "maps": "https://maps.google.com",
    "github": "https://github.com", "whatsapp": "https://web.whatsapp.com",
    "chatgpt": "https://chat.openai.com", "claude": "https://claude.ai",
    "facebook": "https://www.facebook.com", "instagram": "https://www.instagram.com",
    "twitter": "https://twitter.com", "x": "https://x.com",
}
APPS = {
    "notepad": "notepad", "calculator": "calc", "calc": "calc",
    "paint": "mspaint", "chrome": "chrome", "explorer": "explorer",
    "file explorer": "explorer", "cmd": "cmd", "command prompt": "cmd",
    "settings": "ms-settings:", "word": "winword", "excel": "excel",
    "powerpoint": "powerpnt", "spotify": "spotify",
}

# ---- Images: recognition & creation -------------------------------
# Where created images are saved.
IMAGE_SAVE_FOLDER = os.path.join(os.path.expanduser("~"), "Pictures", "SmithAI")
# Free image generation (no API key needed; uses the internet).
IMAGE_GEN_URL = "https://image.pollinations.ai/prompt/"
# Local vision model for recognising images (run: ollama pull llava).
VISION_MODEL = "llava"

# ---- Local AI brain (Ollama) --------------------------------------
USE_AI_BRAIN = True
AI_MODEL = "llama3.2"
OLLAMA_URL = "http://localhost:11434/api/generate"

# ---- ChatGPT / OpenAI brain (optional) ----------------------------
# If you have an OpenAI API key, set USE_OPENAI = True and paste your key.
# Then Smith answers with ChatGPT and doesn't need Ollama running.
# KEEP THIS FILE PRIVATE once your key is in it.
# ---- GitHub Models AI brain --------------------------------------
USE_GITHUB_MODELS = True

# Paste your NEW GitHub token here
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
# Best free models:
# gpt-4o-mini
# Phi-4-mini-instruct
# DeepSeek-R1
# Llama-3.3-70B-Instruct
GITHUB_MODEL = "gpt-4o-mini"
# ---- Gemini API -----------------------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

# ---- Natural human voice (edge-tts: free, no key, needs internet) -
USE_EDGE_TTS = True               # set False to use the offline robotic voice
EDGE_VOICE = "en-US-AriaNeural"   # try en-GB-SoniaNeural, en-US-JennyNeural

# ---- Weather & morning briefing -----------------------------------
WEATHER_CITY = "Hyderabad"        # used for the morning briefing
BRIEFING_HOUR = 8                 # auto-briefing hour (24h) in background; None = off

# ---- Reading text (OCR) -------------------------------------------
# Install Tesseract once: https://github.com/UB-Mannheim/tesseract/wiki
TESSERACT_PATH = r"C:/Program Files/Tesseract-OCR/tesseract.exe"

# ====================================================================
#  --- You normally do NOT need to edit below this line ---
# ====================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"),
              logging.StreamHandler()],
)
log = logging.getLogger("assistant")

# Optional packages (degrade gracefully if missing)
try:
    import psutil
except ImportError:
    psutil = None
try:
    from plyer import notification as _notifier
except ImportError:
    _notifier = None


# ====================================================================
#  SPEAKING  (soft & gentle)
# ====================================================================
_tts_engine = None


def _get_voice_engine():
    global _tts_engine
    if _tts_engine is None:
        import pyttsx3
        _tts_engine = pyttsx3.init()
        _tts_engine.setProperty("rate", SPEAK_SPEED)
        _tts_engine.setProperty("volume", SPEAK_VOLUME)
        if SOFT_VOICE:
            try:
                for v in _tts_engine.getProperty("voices"):
                    name = (getattr(v, "name", "") or "").lower()
                    if any(p in name for p in ("zira", "hazel", "female", "susan", "aria")):
                        _tts_engine.setProperty("voice", v.id)
                        break
            except Exception:
                pass
    return _tts_engine


_mixer_ready = False


def _edge_speak(text: str) -> bool:
    """Speak with the natural edge-tts voice. Returns True if it spoke."""
    try:
        import asyncio
        import tempfile
        import time as _t
        import edge_tts
        import pygame
    except Exception:
        return False
    global _mixer_ready
    try:
        path = os.path.join(tempfile.gettempdir(), f"smith_tts_{int(_t.time()*1000)}.mp3")

        async def _gen():
            await edge_tts.Communicate(text, EDGE_VOICE).save(path)

        asyncio.run(_gen())
        if not _mixer_ready:
            pygame.mixer.init()
            _mixer_ready = True
        pygame.mixer.music.load(path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            _t.sleep(0.1)
        try:
            pygame.mixer.music.unload()
            os.remove(path)
        except Exception:
            pass
        return True
    except Exception as e:
        log.warning("edge-tts failed (%s); using offline voice.", e)
        return False


def _pyttsx3_speak(text: str) -> bool:
    try:
        engine = _get_voice_engine()
        engine.say(text)
        engine.runAndWait()
        return True
    except Exception:
        return False


def _powershell_speak(text: str) -> bool:
    """Speak using Windows' built-in voice. Needs NO extra packages."""
    if os.name != "nt":
        return False
    try:
        safe = text.replace("'", "''")
        cmd = ("Add-Type -AssemblyName System.Speech; "
               "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
               f"$s.Rate = -1; $s.Speak('{safe}')")
        subprocess.run(["powershell", "-NoProfile", "-Command", cmd], check=False)
        return True
    except Exception:
        return False


def speak(text: str) -> None:
    if not SPEAK_REPLIES or not text:
        return
    # Order matters: edge (natural) -> Windows voice (reliable, separate
    # process, no clash with the mic) -> pyttsx3 (last resort).
    if USE_EDGE_TTS and _edge_speak(text):
        return
    if _powershell_speak(text):
        return
    _pyttsx3_speak(text)


# Conversation memory: the last few turns, so follow-ups make sense.
_recent_turns: list = []


def _remember_turn(role: str, text: str) -> None:
    _recent_turns.append((role, text))
    del _recent_turns[:-20]  # keep last 20 turns


def say(text: str) -> None:
    """Print and speak a reply, and record it for conversation memory."""
    print(text)
    _remember_turn("smith", text)
    speak(text)


def alert(title: str, message: str, speak_it: bool = True) -> None:
    """Background alert: log, show a desktop pop-up, optionally speak."""
    log.info("%s -- %s", title, message)
    if SHOW_NOTIFICATIONS and _notifier is not None:
        try:
            _notifier.notify(title=title, message=message, timeout=8)
        except Exception as e:
            log.warning("Notification failed: %s", e)
    if speak_it and SPEAK_ALERTS:
        speak(f"{title}. {message}")


# ====================================================================
#  MEMORY & PERSONALITY
# ====================================================================
def load_memory() -> dict:
    try:
        import json
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"name": USER_NAME, "notes": []}


def save_memory(mem: dict) -> None:
    try:
        import json
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(mem, f, indent=2, ensure_ascii=False)
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
    if h < 12:
        return "Good morning"
    if h < 17:
        return "Good afternoon"
    if h < 21:
        return "Good evening"
    return "Hello"


def greet() -> None:
    name = user_name()
    hello = time_greeting()
    if name:
        say(f"{hello}, {name}. I'm so glad you're here. How can I help you?")
    else:
        say(f"{hello}. I'm {ASSISTANT_NAME}, your assistant. "
            f"I'd love to know your name. You can say, my name is, and then your name.")


def handle_personal(text: str) -> bool:
    """Greetings, feelings, memory, and 'what am I doing'. Returns True if handled."""
    low = text.lower().strip()

    # Remember something
    note = _after(low, ("remember that ", "remember ", "note that ",
                        "don't forget that ", "dont forget that "))
    if note:
        mem = load_memory()
        mem.setdefault("notes", []).append(note)
        save_memory(mem)
        name = user_name()
        say(f"Of course{', ' + name if name else ''}. I'll remember that for you.")
        return True

    # Your name
    not_names = {"tired", "sad", "happy", "good", "fine", "okay", "ok", "great",
                 "excited", "lonely", "stressed", "upset", "busy", "hungry",
                 "sleepy", "angry", "bored", "sick", "down", "low", "nervous",
                 "scared", "worried", "feeling", "here", "back", "sorry"}
    name_said = _after(low, ("my name is ", "call me ", "i am ", "i'm ", "im "))
    nw = name_said.split()
    if (name_said and 1 <= len(nw) <= 3 and name_said.replace(" ", "").isalpha()
            and not any(w in not_names for w in nw)):
        new_name = name_said.title()
        mem = load_memory()
        mem["name"] = new_name
        save_memory(mem)
        say(f"It's wonderful to meet you, {new_name}. I'll remember you.")
        return True

    # Recall
    if any(p in low for p in ("what do you know about me", "what do you remember",
                              "what have i told you", "tell me about myself")):
        mem = load_memory()
        name, notes = mem.get("name", ""), mem.get("notes", [])
        parts = []
        if name:
            parts.append(f"I know your name is {name}")
        if notes:
            parts.append("you told me: " + "; ".join(notes))
        say(". ".join(parts) + "." if parts
            else "You haven't shared much with me yet, but I'd love to learn about you.")
        return True

    # What am I doing
    if any(p in low for p in ("what am i doing", "what am i working on",
                              "what's on my screen", "whats on my screen",
                              "what am i using")):
        title = get_active_window_title()
        say(f"You're currently using {title}." if title
            else "I can't tell what's on your screen right now.")
        return True

    # Check email on request
    if any(p in low for p in ("check my email", "check email", "any new email",
                              "any new emails", "read my email", "read my emails",
                              "new emails")):
        if EMAIL_ENABLED:
            check_email_once(always_report=True)
        else:
            say("Email isn't set up yet. You can turn it on in the settings.")
        return True

    # Greetings
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
    if low in ("bye", "goodbye", "good night", "see you"):
        name = user_name()
        say(f"Take care{', ' + name if name else ''}. I'll be right here when you need me.")
        return True

    # Feelings
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
            f"I'm here with you. Would you like to talk about it, or shall I help "
            f"take your mind off it?")
        return True
    if any(c in low for c in happy):
        say("That makes me so happy to hear. Thank you for sharing that with me.")
        return True

    return False

def ask_gemini(question: str) -> str:
    """Ask Gemini and return its answer."""
    try:
        headers = {"Content-Type": "application/json"}
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
        url = f"{GEMINI_URL}?key={GEMINI_API_KEY}"
        r = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=30
        )
        if r.status_code != 200:
            return ""
        data = r.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        log.warning("Gemini failed: %s", e)
        return ""


def ask_github_models(question: str, with_context: bool = False) -> str:
    """Answer using GitHub Models."""
    if not USE_GITHUB_MODELS:
        return ""
    try:
        messages = [
            {
                "role": "system",
                "content": (
                        f"You are {ASSISTANT_NAME}, a warm, smart, helpful AI assistant. "
                        f"Reply naturally and briefly.\n\n"
                        "IMPORTANT RULES:\n"
                        "- The user may have spelling mistakes. ALWAYS understand their intent and answer correctly, never point out the spelling error.\n"
                        "- If the user says 'it', 'that', 'this', 'change it', 'make it', 'the same', refer to what was discussed just before.\n"
                        "- Use the conversation history to understand follow-up questions.\n\n"
                        "For mathematics:\n"
                    "- use proper LaTeX\n"
                    "- use $$ equation $$ blocks\n"
                    "- do NOT escape backslashes\n"
                    + _memory_context()
                )
            }
        ]
        if with_context and _recent_turns:
            conversation = ""
            for role, txt in _recent_turns[-14:]:
                if role == "you":
                    conversation += f"User: {txt}\n"
                else:
                    conversation += f"Assistant: {txt}\n"
            conversation += f"User: {question}"
            messages.append({
                "role": "user",
                "content": (
                    "Continue the conversation naturally.\n"
                    "If the user says things like "
                    "'step by step', 'explain more', "
                    "'continue', 'why', or 'solve it', "
                    "refer to the PREVIOUS question.\n\n"
                    + conversation
                )
            })
        else:
            messages.append({
                "role": "user",
                "content": question
            })
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Content-Type": "application/json"
        }
        payload = {
            "messages": messages,
            "model": GITHUB_MODEL,
            "temperature": 0.7,
            "max_tokens": 1500,
        }
        response = requests.post(
            "https://models.inference.ai.azure.com/chat/completions",
            headers=headers,
            json=payload,
            timeout=60
        )
        if response.status_code != 200:
            log.warning("GitHub Models failed: %s", response.text)
            return ""
        data = response.json()
        answer = data["choices"][0]["message"]["content"].strip()
        _remember_turn("you", question)
        _remember_turn("smith", answer)
        return answer
    except Exception as e:
        log.warning("GitHub Models failed: %s", e)
        return ""
def analyze_and_pick(question: str, ans1: str, ans2: str) -> str:
    """Send both answers to GPT and get the best combined answer."""
    if not ans1 and not ans2:
        return "Both AIs failed to answer."
    if not ans1:
        return ans2
    if not ans2:
        return ans1

    prompt = f"""
A user asked: "{question}"

AI 1 (GPT-4o) answered:
{ans1}

AI 2 (Gemini) answered:
{ans2}

Your job:
1. Analyze both answers carefully
2. Find which is more accurate and complete
3. Combine the best parts of both
4. Give ONE perfect final answer
5. Do NOT mention which AI said what
Just give the best final answer directly.
"""
    try:
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Content-Type": "application/json"
        }
        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert answer analyzer."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "model": GITHUB_MODEL,
            "max_tokens": 1500
        }
        r = requests.post(
            "https://models.inference.ai.azure.com/chat/completions",
            headers=headers,
            json=payload,
            timeout=60
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
        return ans1
    except Exception:
        return ans1
def ask_bluesminds(question: str, with_context: bool = False) -> str:
    """Bluesminds coding AI (gpt-5-chat)."""
    try:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an elite coding AI like Cursor or GitHub Copilot.\n"
                    "- Write complete, working code always — no placeholders.\n"
                    "- Use markdown code blocks with language tags (```python, ```js etc).\n"
                    "- When debugging: explain the bug, then show the full fixed code.\n"
                    "- After code, give a short plain-English explanation.\n"
                    "- If user says 'fix it', 'improve it', 'add to it' — refer to the previous code.\n"
                    "- Auto-detect the programming language from context.\n"
                )
            }
        ]
        if with_context and _recent_turns:
            conversation = ""
            for role, txt in _recent_turns[-14:]:
                conversation += f"{'User' if role == 'you' else 'Assistant'}: {txt}\n"
            conversation += f"User: {question}"
            messages.append({"role": "user", "content": conversation})
        else:
            messages.append({"role": "user", "content": question})
        headers = {
            "Authorization": f"Bearer {BLUESMINDS_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": BLUESMINDS_MODEL,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 4000
        }
        r = requests.post(BLUESMINDS_URL, headers=headers, json=payload, timeout=60)
        if r.status_code != 200:
            log.warning("Bluesminds failed: %s", r.text)
            return ""
        answer = r.json()["choices"][0]["message"]["content"].strip()
        _remember_turn("you", question)
        _remember_turn("assistant", answer)
        return answer
    except Exception as e:
        log.warning("Bluesminds failed: %s", e)
        return ""

def ask_ollama(question: str) -> str:
    """Ask the local Ollama model as a fallback."""
    if not USE_AI_BRAIN:
        return ""
    try:
        import json, urllib.request
        payload = json.dumps({
            "model": AI_MODEL,
            "prompt": question,
            "stream": False
        }).encode()
        req = urllib.request.Request(
            OLLAMA_URL, data=payload,
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode()).get("response", "").strip()
    except Exception as e:
        log.warning("Ollama failed: %s", e)
        return ""
def ask_ai_brain(question: str, with_context: bool = False) -> str:
    """Ask Hermes first, then GitHub+Gemini."""

    import threading




    # ===== FALLBACK =====
    results = {"gpt": "", "gemini": ""}

    def get_gpt():
        results["gpt"] = ask_github_models(question, with_context)

    def get_gemini():
        results["gemini"] = ask_gemini(question)

    # Run both simultaneously
    t1 = threading.Thread(target=get_gpt)
    t2 = threading.Thread(target=get_gemini)

    t1.start()
    t2.start()

    t1.join()
    t2.join()

    final = analyze_and_pick(
        question,
        results["gpt"],
        results["gemini"]
    )

    if not final or final == "Both AIs failed to answer.":
        final = ask_ollama(question)

    _remember_turn("you", question)
    _remember_turn("smith", final)

    return final

def open_url(url: str) -> None:
    try:
        webbrowser.get(CHROME_PATH).open(url)
    except Exception:
        webbrowser.open(url)


def launch_app(command: str) -> bool:
    try:
        subprocess.Popen(f'start "" {command}', shell=True)
        return True
    except Exception:
        return False


def get_open_target(question: str):
    low = question.lower().strip()
    for word in OPEN_WORDS:
        if low.startswith(word + " "):
            return low[len(word):].strip()
    return None


def do_open(target: str) -> None:
    name = target.lower().strip()
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
    say(f"Trying to open {name}")
    if not launch_app(name):
        say("I could not find that app, so I am searching the web instead")
        open_url(SEARCH_ENGINE + urllib.parse.quote(target))


def _open_file(path: str) -> None:
    try:
        if os.name == "nt":
            os.startfile(path)  # noqa
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass


def _image_exts():
    return (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp")


def newest_image(folder: str) -> str:
    """Return the most recently changed image file in a folder."""
    try:
        files = [os.path.join(folder, f) for f in os.listdir(folder)
                 if f.lower().endswith(_image_exts())]
        return max(files, key=os.path.getmtime) if files else ""
    except Exception:
        return ""


def _extract_image_path(text: str) -> str:
    for token in text.replace('"', " ").split():
        if token.lower().endswith(_image_exts()):
            return token
    return ""


def create_image(prompt: str) -> str:
    import os, time, requests, urllib.parse

    os.makedirs(IMAGE_SAVE_FOLDER, exist_ok=True)
    out = os.path.join(IMAGE_SAVE_FOLDER, f"image_{int(time.time())}.png")

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0 Safari/537.36"}

    urls = [
        "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt) + "?width=1024&height=1024&nologo=true&seed=" + str(int(time.time())),
        "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt) + "?model=flux&width=1024&height=1024&nologo=true",
        "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt),
    ]

    for url in urls:
        try:
            r = requests.get(url, headers=headers, timeout=120)
            print("Image status:", r.status_code)
            if r.status_code == 200 and len(r.content) > 1000:
                with open(out, "wb") as f:
                    f.write(r.content)
                return out
        except Exception as e:
            print("IMAGE ERROR:", repr(e))
            continue

    return None

def describe_image(path: str) -> None:
    """Describe what's in an image using the local vision model."""
    if not path or not os.path.isfile(path):
        say("I couldn't find that image. Tell me the file name, or put it in Downloads.")
        return
    import base64
    import json
    import urllib.request
    say("Let me look at that image.")
    try:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        payload = json.dumps({
            "model": VISION_MODEL,
            "prompt": "Describe what is in this image in one or two short sentences.",
            "images": [b64], "stream": False,
        }).encode()
        req = urllib.request.Request(OLLAMA_URL, data=payload,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            desc = json.loads(r.read().decode()).get("response", "").strip()
        say(desc or "I couldn't tell what's in the image.")
    except Exception as e:
        log.warning("Vision failed: %s", e)
        say("I couldn't analyse the image. Make sure the vision model is installed "
            "by running: ollama pull llava")


def describe_screen() -> None:
    """Take a screenshot and describe what's on your screen."""
    try:
        from PIL import ImageGrab
    except ImportError:
        say("To see your screen I need the Pillow package. Run: pip install pillow")
        return
    import tempfile
    try:
        shot = ImageGrab.grab()
        tmp = os.path.join(tempfile.gettempdir(), "smith_screen.png")
        shot.save(tmp)
        describe_image(tmp)
    except Exception as e:
        log.warning("Screenshot failed: %s", e)
        say("I couldn't capture your screen right now.")


def _fuzzy_fix(text: str) -> str:
    """Auto-correct common misspellings using difflib."""
    import difflib
    corrections = {
        "creat": "create", "crate": "create", "ceate": "create",
        "generat": "generate", "generete": "generate", "gnerate": "generate",
        "imge": "image", "iamge": "image", "imgae": "image", "imag": "image",
        "pictur": "picture", "pictue": "picture", "picter": "picture",
        "mak": "make", "maek": "make",
        "drwa": "draw", "drow": "draw",
        "an": "an", "a": "a", "of": "of",
    }
    words = text.split()
    fixed = []
    for w in words:
        if w in corrections:
            fixed.append(corrections[w])
        else:
            fixed.append(w)
    return " ".join(fixed)

_last_image_prompt = ""
def handle_images(text: str) -> bool:
    global _last_image_prompt
    low = text.lower().strip()
    low = _fuzzy_fix(low)

    triggers = [
        "create an image of",
        "create image of",
        "create a image of",
        "generate an image of",
        "generate image of",
        "generate a image of",
        "draw",
        "draw me",
        "make an image of",
        "make a image of",
        "make image of",
        "can you create an image of",
        "can you draw",
        "can you generate",
        "show me an image of",
        "show me a image of",
        "create picture of",
        "make a picture of",
        "generate a picture of",
        "image of",
        "picture of",
    ]

    for t in triggers:

        if t in low:

            prompt = low.split(t, 1)[1].strip()

            if not prompt:
                prompt = "robot"

            _last_image_prompt = prompt
            img = create_image(prompt)

            if img:
                say(f"[IMAGE]{img}")
            else:
                say("Image creation failed.")

            return True

        # Check if user is editing the last image
    edit_triggers = [
        "make it", "change it", "change the", "put the", "make the",
        "add", "remove", "set the", "color it", "colour it",
        "now make", "now change", "now add", "but", "instead",
    ]
    if _last_image_prompt and any(low.startswith(t) or t in low for t in edit_triggers):
        new_prompt = _last_image_prompt + ", " + low

        _last_image_prompt = new_prompt
        img = create_image(new_prompt)
        if img:
            say(f"[IMAGE]{img}")
        else:
            say("Image creation failed.")
        return True

    return False


def _press_key(code: int) -> None:
    """Send a Windows virtual key (for volume/media keys)."""
    if os.name != "nt":
        return
    try:
        import ctypes
        u = ctypes.windll.user32
        u.keybd_event(code, 0, 0, 0)
        u.keybd_event(code, 0, 2, 0)  # key up
    except Exception:
        pass


# Virtual key codes
VK_VOL_UP, VK_VOL_DOWN, VK_MUTE = 0xAF, 0xAE, 0xAD
VK_PLAY_PAUSE, VK_NEXT, VK_PREV = 0xB3, 0xB0, 0xB1


def lock_computer() -> None:
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.user32.LockWorkStation()
        except Exception:
            pass


def set_brightness(delta: int = 0, value=None) -> None:
    try:
        import screen_brightness_control as sbc
    except ImportError:
        say("To control brightness, run: pip install screen-brightness-control")
        return
    try:
        cur = sbc.get_brightness()
        cur = cur[0] if isinstance(cur, (list, tuple)) else cur
        new = value if value is not None else max(0, min(100, int(cur) + delta))
        sbc.set_brightness(new)
        say(f"Brightness set to {new} percent.")
    except Exception as e:
        log.warning("Brightness failed: %s", e)
        say("I couldn't change the brightness.")


def type_text(text: str) -> None:
    """Type text into whatever window you click on."""
    try:
        import pyautogui
        import time as _t
    except ImportError:
        say("To type for you, run: pip install pyautogui")
        return
    say("Okay, I'll start typing in 3 seconds. Click where you want the text.")
    import time as _t
    _t.sleep(3)
    try:
        pyautogui.write(text, interval=0.02)
    except Exception as e:
        log.warning("Typing failed: %s", e)


def _grab_screen(path: str = "") -> str:
    """Save a screenshot, return its path (or '')."""
    try:
        from PIL import ImageGrab
    except ImportError:
        say("I need the Pillow package for that. Run: pip install pillow")
        return ""
    import tempfile
    import time as _t
    path = path or os.path.join(tempfile.gettempdir(), f"smith_screen_{int(_t.time())}.png")
    try:
        ImageGrab.grab().save(path)
        return path
    except Exception as e:
        log.warning("Screenshot failed: %s", e)
        return ""


def take_screenshot() -> None:
    import time as _t
    os.makedirs(IMAGE_SAVE_FOLDER, exist_ok=True)
    path = os.path.join(IMAGE_SAVE_FOLDER, f"screenshot_{int(_t.time())}.png")
    if _grab_screen(path):
        say("I've taken a screenshot and saved it for you.")
        _open_file(path)


def read_text_from_image(path: str) -> None:
    """Read (OCR) the text in an image and tell you what it says."""
    if not path or not os.path.isfile(path):
        say("I couldn't find an image to read.")
        return
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        say("To read text I need pytesseract. Run: pip install pytesseract pillow")
        return
    if os.name == "nt" and os.path.isfile(TESSERACT_PATH):
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
    try:
        text = pytesseract.image_to_string(Image.open(path)).strip()
        if text:
            say("Here's the text I found:")
            say(text[:600])
        else:
            say("I couldn't find any readable text in that.")
    except Exception as e:
        log.warning("OCR failed: %s", e)
        say("I couldn't read the text. Make sure Tesseract is installed "
            "(see the README) and the path in settings is correct.")


def read_screen_text() -> None:
    path = _grab_screen()
    if path:
        read_text_from_image(path)


def get_weather(city: str = None) -> str:
    """Get a short weather line (free, no key)."""
    import urllib.request
    city = city or WEATHER_CITY
    url = f"https://wttr.in/{urllib.parse.quote(city)}?format=%l:+%C+%t"
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            return r.read().decode("utf-8", "ignore").strip()
    except Exception:
        return ""


def _count_unseen_email():
    if not EMAIL_ENABLED:
        return None
    import imaplib
    try:
        M = imaplib.IMAP4_SSL(IMAP_SERVER)
        M.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
        M.select("INBOX")
        _, data = M.search(None, "UNSEEN")
        n = len(data[0].split())
        M.close()
        M.logout()
        return n
    except Exception:
        return None


def daily_briefing() -> None:
    import datetime
    name = user_name()
    parts = [f"{time_greeting()}{', ' + name if name else ''}."]
    parts.append("It's " + datetime.datetime.now().strftime("%A, %I:%M %p") + ".")
    w = get_weather()
    if w:
        parts.append("Weather: " + w + ".")
    n = _count_unseen_email()
    if n is not None:
        parts.append(f"You have {n} unread email{'s' if n != 1 else ''}.")
    rem = load_memory().get("reminders", [])
    if rem:
        parts.append(f"You have {len(rem)} reminder{'s' if len(rem) != 1 else ''} pending.")
    say(" ".join(parts))


def translate(text: str) -> None:
    reply = ask_ai_brain(
        "Act as a translator. " + text +
        ". Reply with only the translation, plus a simple pronunciation if helpful.")
    if reply:
        say(reply)
    else:
        say("I couldn't translate that. Make sure the AI brain (Ollama) is running.")


# ---- Reminders ----------------------------------------------------
def _clean_what(s: str) -> str:
    s = s.strip(" .,")
    if s.lower().startswith("to "):
        s = s[3:]
    return s or "your reminder"


def _parse_when(text: str):
    """Return (due_epoch, what_text) or (None, text)."""
    import re
    import time as _t
    import datetime
    low = text.lower()
    now = datetime.datetime.now()

    m = re.search(r"\bin\s+(\d+)\s*(seconds?|secs?|minutes?|mins?|hours?|hrs?)\b", low)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        if unit.startswith(("hour", "hr")):
            secs = n * 3600
        elif unit.startswith(("min",)):
            secs = n * 60
        elif unit.startswith(("sec",)):
            secs = n
        else:
            secs = n * 60
        what = re.sub(r"\bin\s+\d+\s*\w+\b", "", text).strip()
        return (_t.time() + secs, _clean_what(what))

    m = re.search(r"\bat\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", low)
    if m:
        h, mins, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3)
        if ap == "pm" and h < 12:
            h += 12
        if ap == "am" and h == 12:
            h = 0
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
    """Reminders, media/volume/brightness, lock, type, screenshot, OCR, translate."""
    low = text.lower().strip()

    # Type for you (needs original case)
    if low.startswith("type "):
        payload = text[5:].strip()
        if payload:
            type_text(payload)
            return True

    # Reminders
    r = _after(low, ("remind me to ", "remind me ", "set a reminder to ",
                     "set a reminder ", "set an alarm to ", "set an alarm "))
    if r:
        add_reminder(r)
        return True

    # Volume
    if any(k in low for k in ("volume up", "turn it up", "louder")):
        for _ in range(5):
            _press_key(VK_VOL_UP)
        say("Volume up.")
        return True
    if any(k in low for k in ("volume down", "turn it down", "quieter", "lower the volume")):
        for _ in range(5):
            _press_key(VK_VOL_DOWN)
        say("Volume down.")
        return True
    if low in ("mute", "unmute", "mute volume", "mute the volume"):
        _press_key(VK_MUTE)
        say("Done.")
        return True

    # Music / media
    if "play music" in low:
        say("Opening your music.")
        launch_app("spotify")
        return True
    if low in ("pause", "play", "resume", "pause music", "play pause", "pause the music"):
        _press_key(VK_PLAY_PAUSE)
        say("Okay.")
        return True
    if any(k in low for k in ("next song", "next track")) or low == "next":
        _press_key(VK_NEXT)
        say("Next track.")
        return True
    if any(k in low for k in ("previous song", "previous track")) or low == "previous":
        _press_key(VK_PREV)
        say("Previous track.")
        return True

    # Brightness
    if "brightness up" in low or "brighter" in low:
        set_brightness(delta=20)
        return True
    if "brightness down" in low or "dimmer" in low or "lower the brightness" in low:
        set_brightness(delta=-20)
        return True

    # Lock
    if any(k in low for k in ("lock my computer", "lock the computer", "lock my pc",
                              "lock screen", "lock the screen")):
        say("Locking your computer.")
        lock_computer()
        return True

    # Screenshot
    if any(k in low for k in ("take a screenshot", "take screenshot", "screenshot",
                              "capture my screen", "capture the screen")):
        take_screenshot()
        return True

    # OCR (read text)
    if any(k in low for k in ("read the text on my screen", "read text on my screen",
                              "read my screen", "read the screen", "read text from screen")):
        read_screen_text()
        return True
    if low.startswith(("read the text from ", "read text from ", "read text in ",
                       "read the text in ")):
        path = _extract_image_path(text) or newest_image(WATCH_FOLDER)
        read_text_from_image(path)
        return True
    if low in ("read this", "read this image", "read the image", "read this picture"):
        path = newest_image(WATCH_FOLDER) or newest_image(IMAGE_SAVE_FOLDER)
        read_text_from_image(path)
        return True

    # Morning briefing
    if any(k in low for k in ("daily briefing", "brief me", "my briefing",
                              "morning briefing", "give me a briefing")):
        daily_briefing()
        return True

    # Translation
    if low.startswith("translate ") or "how do you say" in low or "how do i say" in low:
        translate(text)
        return True

    return False


def needs_web(question: str) -> bool:
    """Only go to the web for things that need fresh info."""
    low = question.lower()
    return any(t in low for t in SEARCH_TRIGGER_WORDS)


def handle_basics(text: str) -> bool:
    """Answer simple things locally (no internet, no Ollama needed)."""
    import datetime
    import re
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

    # Simple math: "what is 5 plus 3", "12 divided by 4"
    expr = low
    for word, sym in (("multiplied by", "*"), ("divided by", "/"),
                      ("plus", "+"), ("minus", "-"), ("times", "*")):
        expr = expr.replace(word, sym)
    expr = re.sub(r"(what is|whats|what's|calculate|compute|how much is)", "", expr)
    expr = expr.strip(" ?")
    if expr and re.fullmatch(r"[0-9\.\s\+\-\*\/\(\)]+", expr):
        try:
            result = eval(expr, {"__builtins__": {}}, {})  # math only
            say(f"That's {result}.")
            return True
        except Exception:
            pass

    return False


def answer(question: str) -> None:
    question = question.strip()
    if not question:
        return
    _remember_turn("you", question)
    if handle_personal(question):
        return
    if handle_commands(question):
        return
    if handle_basics(question):
        return
    if handle_images(question):
        return
    target = get_open_target(question)
    if target:
        do_open(target)
        return
    if needs_web(question):
        say("Let me search the web for that.")
        search_in_chrome(question)
    else:
        reply = ask_ai_brain(question, with_context=True)
        if reply:
            say(reply)
        else:
            say("Let me search the web for that.")
            search_in_chrome(question)


def answer_OLD_UNUSED(question: str) -> None:
    pass


# ====================================================================
#  WATCHERS
# ====================================================================
def start_folder_watcher() -> None:
    if not WATCH_FOLDER_ENABLED:
        return
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
    except ImportError:
        log.warning("Folder watching needs 'watchdog'. Run: pip install watchdog")
        return

    class Handler(FileSystemEventHandler):
        def on_created(self, event):
            if not event.is_directory:
                alert("New file", os.path.basename(event.src_path))

        def on_modified(self, event):
            if not event.is_directory:
                alert("File changed", os.path.basename(event.src_path), speak_it=False)

    if not os.path.isdir(WATCH_FOLDER):
        log.warning("Watch folder does not exist: %s", WATCH_FOLDER)
        return
    obs = Observer()
    obs.schedule(Handler(), WATCH_FOLDER, recursive=False)
    obs.daemon = True
    obs.start()
    log.info("Watching folder: %s", WATCH_FOLDER)


_warned = {"cpu": False, "ram": False, "disk": False}


def check_system_once() -> None:
    if psutil is None or not WATCH_SYSTEM_ENABLED:
        return
    readings = {
        "cpu": (psutil.cpu_percent(interval=None), CPU_LIMIT_PERCENT),
        "ram": (psutil.virtual_memory().percent, RAM_LIMIT_PERCENT),
        "disk": (psutil.disk_usage(os.path.abspath(os.sep)).percent, DISK_LIMIT_PERCENT),
    }
    for name, (value, limit) in readings.items():
        if value >= limit and not _warned[name]:
            alert(f"High {name.upper()} usage", f"{name.upper()} at {value:.0f} percent")
            _warned[name] = True
        elif value < limit:
            _warned[name] = False


_email_last_unseen = -1


def _decode_header(raw: str) -> str:
    from email.header import decode_header
    out = []
    for part, enc in decode_header(raw or ""):
        out.append(part.decode(enc or "utf-8", errors="ignore")
                   if isinstance(part, bytes) else part)
    return "".join(out)


def check_email_once(always_report: bool = False) -> None:
    """Check for unread email and alert. Never marks mail as read."""
    global _email_last_unseen
    if not EMAIL_ENABLED:
        return
    import imaplib
    import email
    try:
        M = imaplib.IMAP4_SSL(IMAP_SERVER)
        M.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
        M.select("INBOX")
        _, data = M.search(None, "UNSEEN")
        ids = data[0].split()
        count = len(ids)

        new_arrived = _email_last_unseen >= 0 and count > _email_last_unseen
        if (new_arrived or always_report) and count > 0:
            _, md = M.fetch(ids[-1], "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])")
            msg = email.message_from_bytes(md[0][1])
            frm = _decode_header(msg.get("From", ""))
            subj = _decode_header(msg.get("Subject", "(no subject)"))
            alert("Email", f"You have {count} unread. Latest from {frm}: {subj}")
        elif always_report:
            say("You have no unread emails right now.")

        _email_last_unseen = count
        M.close()
        M.logout()
    except Exception as e:
        log.warning("Email check failed: %s", e)
        if always_report:
            say("I couldn't check your email. Please check the email settings.")


def get_active_window_title() -> str:
    """Title of the window you're currently using (Windows only)."""
    if os.name != "nt":
        return ""
    try:
        import ctypes
        u = ctypes.windll.user32
        hwnd = u.GetForegroundWindow()
        n = u.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(n + 1)
        u.GetWindowTextW(hwnd, buf, n + 1)
        return buf.value
    except Exception:
        return ""


_last_active = ""


def check_activity_once() -> None:
    global _last_active
    if not ACTIVITY_ENABLED:
        return
    title = get_active_window_title()
    if title and title != _last_active:
        _last_active = title
        log.info("Activity: %s", title)
        if ANNOUNCE_ACTIVITY:
            alert("You're now using", title)


# ====================================================================
#  MODES
# ====================================================================
def _watchers_setup() -> None:
    start_folder_watcher()
    if psutil is not None:
        psutil.cpu_percent(interval=None)  # warm up


def _watchers_loop() -> None:
    import datetime
    last = {"sys": 0.0, "email": 0.0, "act": 0.0, "brief_date": None}
    while True:
        now = time.time()
        if now - last["sys"] >= SYSTEM_CHECK_SECONDS:
            check_system_once()
            last["sys"] = now
        if now - last["email"] >= EMAIL_CHECK_SECONDS:
            check_email_once()
            last["email"] = now
        if now - last["act"] >= ACTIVITY_CHECK_SECONDS:
            check_activity_once()
            last["act"] = now
        if BRIEFING_HOUR is not None:
            today = datetime.date.today()
            if datetime.datetime.now().hour == BRIEFING_HOUR and last["brief_date"] != today:
                daily_briefing()
                last["brief_date"] = today
        time.sleep(1)


def run_background() -> None:
    log.info("=" * 50)
    log.info("%s background mode started.", ASSISTANT_NAME)
    if psutil is None and WATCH_SYSTEM_ENABLED:
        log.warning("System watching needs 'psutil'. Run: pip install psutil")
    _watchers_setup()
    start_reminder_watcher()
    try:
        _watchers_loop()
    except KeyboardInterrupt:
        log.info("Background mode stopped.")


def chat_loop() -> None:
    start_reminder_watcher()
    greet()
    print("\n(Type 'quit' to stop.)\n")
    while True:
        try:
            q = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if q.lower() in ("quit", "exit", "q", ""):
            break
        answer(q)
    print("Bye!")


def listen_loop() -> None:
    try:
        import json
        import queue
        import sounddevice as sd
        import vosk
    except ImportError:
        print("Voice mode needs: pip install vosk sounddevice")
        return
    if not os.path.isdir(VOSK_MODEL_PATH):
        print("Speech model not found at:", VOSK_MODEL_PATH)
        print("See the README section 'Talking to it with your voice'.")
        return

    vosk.SetLogLevel(-1)
    start_reminder_watcher()
    model = vosk.Model(VOSK_MODEL_PATH)
    rec = vosk.KaldiRecognizer(model, SAMPLE_RATE)
    audio_q: "queue.Queue" = queue.Queue()

    def cb(indata, frames, t, status):
        audio_q.put(bytes(indata))

    greet()
    if WAKE_WORD:
        print(f"Say '{WAKE_WORD}' to wake me. Say 'stop listening' to quit.\n")
    else:
        print("Speak now. Say 'stop listening' to quit.\n")

    try:
        with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=8000,
                               dtype="int16", channels=1, callback=cb):
            while True:
                data = audio_q.get()
                if not rec.AcceptWaveform(data):
                    continue
                text = json.loads(rec.Result()).get("text", "").strip()
                if not text:
                    continue
                print("You said:", text)
                if text in ("stop listening", "quit", "exit", "goodbye"):
                    break
                if WAKE_WORD:
                    if not text.startswith(WAKE_WORD.lower()):
                        continue
                    text = text[len(WAKE_WORD):].strip()
                    if not text:
                        name = user_name()
                        say(f"Yes{', ' + name if name else ''}? I'm listening.")
                        continue
                answer(text)
    except KeyboardInterrupt:
        pass
    say("Goodbye")


# ====================================================================
#  AUTO-START WITH WINDOWS
# ====================================================================
def _startup_bat_path() -> str:
    startup = os.path.join(os.environ.get("APPDATA", ""),
                           r"Microsoft\Windows\Start Menu\Programs\Startup")
    return os.path.join(startup, f"{ASSISTANT_NAME}_assistant.bat")


def install_autostart() -> None:
    if os.name != "nt":
        print("Auto-start is for Windows only.")
        return
    script = os.path.abspath(__file__)
    # Use THIS interpreter's windowless version, so the venv packages work.
    pyw = sys.executable.replace("python.exe", "pythonw.exe")
    if not os.path.exists(pyw):
        pyw = "pythonw"
    bat = _startup_bat_path()
    try:
        with open(bat, "w", encoding="utf-8") as f:
            f.write("@echo off\r\n")
            f.write(f'cd /d "{os.path.dirname(script)}"\r\n')
            f.write(f'start "" "{pyw}" "{script}" --background\r\n')
        print("Auto-start installed. Smith will run quietly each time you log in.")
        print("Created:", bat)
        print("To start it now without rebooting, double-click that .bat file.")
    except Exception as e:
        print("Could not install auto-start:", e)


def uninstall_autostart() -> None:
    bat = _startup_bat_path()
    try:
        if os.path.exists(bat):
            os.remove(bat)
            print("Auto-start removed.")
        else:
            print("Auto-start was not installed.")
    except Exception as e:
        print("Could not remove auto-start:", e)


# ====================================================================
#  SYSTEM TRAY ICON
# ====================================================================
def run_tray() -> None:
    try:
        import pystray
        from PIL import Image, ImageDraw
    except ImportError:
        print("Tray icon needs: pip install pystray pillow")
        print("Running background mode instead.")
        run_background()
        return

    import threading
    threading.Thread(target=lambda: (_watchers_setup(), _watchers_loop()),
                     daemon=True).start()
    start_reminder_watcher()

    # Draw a simple round icon
    img = Image.new("RGB", (64, 64), (32, 34, 48))
    d = ImageDraw.Draw(img)
    d.ellipse((10, 10, 54, 54), fill=(120, 170, 255))

    def on_mute(icon, item):
        global SPEAK_REPLIES, SPEAK_ALERTS
        SPEAK_REPLIES = not SPEAK_REPLIES
        SPEAK_ALERTS = SPEAK_REPLIES

    def on_brief(icon, item):
        threading.Thread(target=daily_briefing, daemon=True).start()

    def on_listen(icon, item):
        threading.Thread(target=listen_loop, daemon=True).start()

    def on_quit(icon, item):
        icon.stop()
        os._exit(0)

    menu = pystray.Menu(
        pystray.MenuItem(lambda item: "Unmute" if not SPEAK_REPLIES else "Mute", on_mute),
        pystray.MenuItem("Talk to me (voice)", on_listen),
        pystray.MenuItem("Daily briefing", on_brief),
        pystray.MenuItem("Quit", on_quit),
    )
    icon = pystray.Icon(ASSISTANT_NAME, img, f"{ASSISTANT_NAME} assistant", menu)
    print(f"{ASSISTANT_NAME} is running in the system tray.")
    icon.run()


# ====================================================================
#  MAIN
# ====================================================================
USAGE = (
    "Modes:\n"
    "  python assistant.py            background mode (watches & alerts)\n"
    "  python assistant.py --tray     run with a system tray icon\n"
    "  python assistant.py --chat     type to it\n"
    "  python assistant.py --voice    talk to it\n"
    "  python assistant.py --install  start automatically with Windows\n"
    "  python assistant.py --uninstall\n"
)


def main() -> None:
    args = sys.argv[1:]
    if args:
        a0 = args[0].lower()
        if a0 in ("--install", "--install-autostart"):
            install_autostart(); return
        if a0 in ("--uninstall", "--remove-autostart"):
            uninstall_autostart(); return
        if a0 in ("--tray", "-t"):
            run_tray(); return
        if a0 in ("--voice", "-v"):
            listen_loop(); return
        if a0 in ("--chat", "-c"):
            chat_loop(); return
        if a0 in ("--background", "-b"):
            run_background(); return
        answer(" ".join(args)); return  # one-shot question

    print(USAGE)
    run_background()


if __name__ == "__main__":
    main()
