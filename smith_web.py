"""
Assist Neo - Web App
Run: python smith_web.py
"""
import os, base64, threading, webbrowser, urllib.parse, uuid, json, subprocess, socket, hashlib

from flask import Flask, request, jsonify, send_from_directory, session, redirect
import assistant

try:
    import requests as _req
except ImportError:
    _req = None

app = Flask(__name__)
BASE = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE, "uploads")
CHATS_DIR = os.path.join(BASE, "chats")
USERS_FILE = os.path.join(BASE, "users.json")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(CHATS_DIR, exist_ok=True)

app.secret_key = hashlib.sha256(b"assistneo_2026_secret").hexdigest()


# ── users ────────────────────────────────────────────────────────
def _load_users():
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def _save_users(u):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(u, f, indent=2)


def _hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()


def _current_user():
    return session.get("username", "")


def _current_nick():
    return session.get("nickname", _current_user().capitalize())


# ── config ───────────────────────────────────────────────────────
SPEAK_ON = False
WEB_SEARCH_ENGINE = "tavily"
WEB_SEARCH_KEY = os.getenv("WEB_SEARCH_KEY")

# ── speech ───────────────────────────────────────────────────────
_speech_proc = None
_speech_lock = threading.Lock()


def web_speak(text):
    global _speech_proc
    if not text or os.name != "nt": return
    safe = text.replace("'", "''")
    cmd = ("Add-Type -AssemblyName System.Speech;$s=New-Object "
           "System.Speech.Synthesis.SpeechSynthesizer;$s.Rate=-1;$s.Speak('%s')" % safe)
    with _speech_lock:
        if _speech_proc and _speech_proc.poll() is None:
            _speech_proc.kill()
        _speech_proc = subprocess.Popen(
            ["powershell", "-NoProfile", "-Command", cmd],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    _speech_proc.wait()


def stop_speaking():
    global _speech_proc
    with _speech_lock:
        if _speech_proc and _speech_proc.poll() is None:
            _speech_proc.kill();
            _speech_proc = None


assistant.speak = web_speak

# ── capture ──────────────────────────────────────────────────────
_capture = []
_lock = threading.Lock()


def _cap(text):
    try:
        assistant._remember_turn("smith", text)
    except:
        pass
    _capture.append(text)


assistant.say = _cap

# ── projects ─────────────────────────────────────────────────────
PROJECTS = {
    "General": "",
    "Coding": "You are an expert software engineer. Help with code and debugging.",
    "Robotics": "You are a robotics expert (Arduino, ESP32). Give safe, practical guidance.",
    "Image Creation": "Help create images. Say 'create an image of ...' to generate one.  create a image of ...   can create an image of....."
}
CURRENT_PROJECT = "General"
_orig_brain = assistant.ask_ai_brain


def _brain(q, with_context=False):

    personality = """
You are a natural conversational AI assistant.

Rules:
- Speak naturally like a human.
- Avoid robotic repetition.
- Do NOT repeatedly ask:
  "Would you like to know more?"
- Continue explanations intelligently.
- If user says:
  yes / ok / continue
  then continue previous topic naturally.
- Be friendly and conversational.
"""

    ctx = PROJECTS.get(CURRENT_PROJECT, "")

    q = personality + "\n\n" + ctx + "\n\nUser: " + q

    return _orig_brain(q, with_context)

# ── web search ───────────────────────────────────────────────────
def _do_search(q):
    if not _req: return []
    try:
        r = _req.post("https://api.tavily.com/search",
                      json={"query": q, "api_key": WEB_SEARCH_KEY, "max_results": 4}, timeout=15)
        return r.json().get("results", []) if r.status_code == 200 else []
    except:
        return []


def _web_answer(question, results):
    if not results or not _req: return None
    ctx = "".join("[%s]\n%s\n\n" % (r.get("title", ""), r.get("content", "")[:500]) for r in results[:4])
    hdrs = {"Authorization": "Bearer %s" % assistant.GITHUB_TOKEN, "Content-Type": "application/json"}
    pl = {"model": assistant.GITHUB_MODEL, "max_tokens": 600,
          "messages": [{"role": "user", "content": "Answer using:\n%s\nQuestion:%s" % (ctx, question)}]}
    try:
        r = _req.post("https://models.inference.ai.azure.com/chat/completions",
                      headers=hdrs, json=pl, timeout=60)
        return r.json()["choices"][0]["message"]["content"].strip() if r.status_code == 200 else None
    except:
        return None


def _smart_search(question):
    if WEB_SEARCH_KEY:
        try:
            results = _do_search(question)
            ans = _web_answer(question, results) if results else None
            if ans: _capture.append(ans); return
        except:
            pass
    _capture.append("Search: https://www.google.com/search?q=" + urllib.parse.quote(question))


assistant.search_in_chrome = _smart_search

# ── file analysis ────────────────────────────────────────────────
_IMG_MIME = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
             "gif": "image/gif", "webp": "image/webp", "bmp": "image/bmp"}
_TXT_EXTS = ("txt", "py", "c", "cpp", "h", "ino", "md", "csv", "json", "log",
             "js", "html", "css", "java", "xml", "yaml", "yml", "ts")


def _img_analyze(path, question):
    ext = path.rsplit(".", 1)[-1].lower()
    mime = _IMG_MIME.get(ext, "image/png")
    if not _req: return "(pip install requests)"
    try:
        b64 = base64.b64encode(open(path, "rb").read()).decode()
        hdrs = {"Authorization": "Bearer %s" % assistant.GITHUB_TOKEN, "Content-Type": "application/json"}
        pl = {"model": assistant.GITHUB_MODEL, "max_tokens": 500,
              "messages": [{"role": "user", "content": [
                  {"type": "text", "text": question or "Describe this image."},
                  {"type": "image_url", "image_url": {"url": "data:%s;base64,%s" % (mime, b64)}}]}]}
        r = _req.post("https://models.inference.ai.azure.com/chat/completions",
                      headers=hdrs, json=pl, timeout=90)
        return r.json()["choices"][0]["message"]["content"].strip() if r.status_code == 200 else "Failed."
    except Exception as e:
        return "(Error: %s)" % e


def _txt_analyze(path, fname, question):
    try:
        content = open(path, "r", encoding="utf-8", errors="ignore").read(8000)
    except Exception as e:
        return "(Cannot read: %s)" % e
    return assistant.ask_ai_brain(
        "Analyse '%s'.\n\nContent:\n%s\n\nRequest:%s" % (fname, content, question or "Explain it.")
    ) or "(No response.)"


# ── chat history (per user) ──────────────────────────────────────
def _user_dir():
    u = _current_user() or "default"
    d = os.path.join(CHATS_DIR, u)
    os.makedirs(d, exist_ok=True)
    return d


def _chat_path(cid):
    return os.path.join(_user_dir(), cid + ".json")


def save_chat(cid, title, messages):
    import time
    try:
        with open(_chat_path(cid), "w", encoding="utf-8") as f:
            json.dump({"id": cid, "title": title, "ts": int(time.time()), "messages": messages},
                      f, indent=2, ensure_ascii=False)
    except:
        pass


def load_chat(cid):
    try:
        with open(_chat_path(cid), "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return None


def list_chats():
    out = []
    try:
        for fn in os.listdir(_user_dir()):
            if fn.endswith(".json"):
                try:
                    d = json.load(open(os.path.join(_user_dir(), fn), encoding="utf-8"))
                    out.append({"id": d["id"], "title": d.get("title", "Chat"), "ts": d.get("ts", 0)})
                except:
                    pass
    except:
        pass
    return sorted(out, key=lambda x: x["ts"], reverse=True)[:30]


LOGO = "data:image/png;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/4gHYSUNDX1BST0ZJTEUAAQEAAAHIAAAAAAQwAABtbnRyUkdCIFhZWiAH4AABAAEAAAAAAABhY3NwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAA9tYAAQAAAADTLQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAlkZXNjAAAA8AAAACRyWFlaAAABFAAAABRnWFlaAAABKAAAABRiWFlaAAABPAAAABR3dHB0AAABUAAAABRyVFJDAAABZAAAAChnVFJDAAABZAAAAChiVFJDAAABZAAAAChjcHJ0AAABjAAAADxtbHVjAAAAAAAAAAEAAAAMZW5VUwAAAAgAAAAcAHMAUgBHAEJYWVogAAAAAAAAb6IAADj1AAADkFhZWiAAAAAAAABimQAAt4UAABjaWFlaIAAAAAAAACSgAAAPhAAAts9YWVogAAAAAAAA9tYAAQAAAADTLXBhcmEAAAAAAAQAAAACZmYAAPKnAAANWQAAE9AAAApbAAAAAAAAAABtbHVjAAAAAAAAAAEAAAAMZW5VUwAAACAAAAAcAEcAbwBvAGcAbABlACAASQBuAGMALgAgADIAMAAxADb/2wBDAAUDBAQEAwUEBAQFBQUGBwwIBwcHBw8LCwkMEQ8SEhEPERETFhwXExQaFRERGCEYGh0dHx8fExciJCIeJBweHx7/2wBDAQUFBQcGBw4ICA4eFBEUHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh7/wAARCAQABAADASIAAhEBAxEB/8QAHQABAAEFAQEBAAAAAAAAAAAAAAYDBAUHCAIBCf/EAGYQAAEDAwIDBAYFBgcJCwgIBwEAAgMEBREGIQcSMRNBUWEIFCIycYFCUpGhsRUjYnLB0RYkM0OCkqIXNFOTssLS0+EJGCVEY3OElKOzwyY1NkZUdIPwJzdFVVZkZYWV8aS0OEdX/8QAHAEBAAIDAQEBAAAAAAAAAAAAAAMEAQIFBgcI/8QASBEAAgEDAQUECQMBBQYFBAMBAAECAwQRIQUSMUFRE2FxkQYUIoGhscHR8DJS4UIVI2Jy8TNTgpKywgcWJEOiVGNz0iWDs/L/2gAMAwEAAhEDEQA/AOMkREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREARF9AJ6AoD4iIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIg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IAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgP/2Q=="


# ── HTML builder (NOT f-string — uses .replace() to avoid brace hell) ──
def _page():
    uname = _current_nick() or "there"
    aname = assistant.ASSISTANT_NAME

    html = """<!DOCTYPE html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ANAME</title>
<script>
MathJax = {
  tex: {
    inlineMath: [['$', '$'], ['\\(', '\\)']],
    displayMath: [['$$', '$$'], ['\\[', '\\]']]
  }
};
</script>
<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
<style>
:root{
--bg:#050505;
--side:#0b0f12;
--pill:#101418;
--txt:#e8fdf5;
--muted:#7aa2a0;

--acc:#00ff88;
--acc2:#00ccff;

--ub:#00b894;
--bb:#11161b;

--bdr:#1f2d36;
--act:#132028;
}
*{box-sizing:border-box;} html,body{height:100%;margin:0;}
body{display:flex;background:var(--bg);color:var(--txt);
  font-family:"Segoe UI",-apple-system,sans-serif;-webkit-font-smoothing:antialiased;}
/* splash */
#splash{position:fixed;inset:0;background:#1a1a20;z-index:9999;display:flex;
  flex-direction:column;align-items:center;justify-content:center;gap:16px;
  animation:splashGo 2.8s ease forwards;}
@keyframes splashGo{0%,60%{opacity:1;}100%{opacity:0;pointer-events:none;}}
.sp-logo{width:110px;height:110px;border-radius:50%;object-fit:cover;
  border:3px solid #00ff88;box-shadow:0 0 40px #3a8cf855;
  animation:spPop 2.8s ease forwards;}
@keyframes spPop{0%{transform:scale(.8);opacity:0;}30%{transform:scale(1.06);opacity:1;}
  50%{transform:scale(1);}100%{opacity:0;}}
.sp-name{
font-size:28px;
font-weight:700;

background:transparent;

color:#00ff88;

text-shadow:
0 0 8px #00ff88,
0 0 18px #00ff88;

animation:spFI .6s .3s ease both;
}
.sp-sub{font-size:14px;color:#9aa0aa;animation:spFI .6s .6s ease both;}
@keyframes spFI{from{opacity:0;transform:translateY(8px);}to{opacity:1;transform:none;}}
/* layout */
.side{width:260px;background:var(--side);display:flex;flex-direction:column;
  padding:14px 10px;flex-shrink:0;border-right:1px solid var(--bdr);overflow-y:auto;}
.side-logo{width:52px;height:52px;border-radius:50%;object-fit:cover;
  border:2px solid var(--bdr);display:block;margin:0 auto 6px;}
.brand{font-size:20px;font-weight:700;padding:8px 10px 14px;color:var(--acc);}
.item{display:flex;align-items:center;gap:10px;width:100%;cursor:pointer;
  background:transparent;color:var(--txt);border:0;border-radius:10px;
  padding:10px 12px;font-size:14px;text-align:left;transition:.12s;}
.item:hover{background:var(--act);}
.newchat{border:1px solid var(--bdr);margin-bottom:6px;}
.sec{color:var(--muted);font-size:11px;padding:16px 12px 6px;letter-spacing:.6px;}
.proj.on,.chat-item.on{background:var(--act);font-weight:600;}
.proj.on .pd{opacity:1!important;}
.pd{width:7px;height:7px;border-radius:50%;background:var(--acc);opacity:0;transition:.15s;}
.chat-item{font-size:13px;padding:8px 12px;}
.chat-item span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.me{margin-top:auto;color:var(--muted);font-size:13px;padding:12px;
  display:flex;align-items:center;gap:8px;}
.dot{width:8px;height:8px;border-radius:50%;background:var(--acc);}
.main{flex:1;display:flex;flex-direction:column;min-width:0;}
.scroll{flex:1;overflow-y:auto;padding:26px 0;}
.thread{max-width:760px;margin:0 auto;padding:0 24px;}
.msg{display:flex;flex-direction:column;margin:14px 0;animation:rise .22s ease both;}
.msg.user{align-items:flex-end;} .msg.bot{align-items:flex-start;}
.bubble{max-width:74%;padding:12px 16px;border-radius:18px;line-height:1.56;
  font-size:15px;white-space:pre-wrap;word-wrap:break-word;}
.user .bubble{background:var(--ub);color:#fff;border-bottom-right-radius:5px;}
.bot  .bubble{
background:var(--bb);
color:var(--txt);
border-bottom-left-radius:5px;
box-shadow:0 0 12px rgba(0,255,136,0.15);
}
.bubble img{max-width:220px;border-radius:10px;display:block;margin-bottom:6px;}
.chip{display:inline-flex;align-items:center;gap:7px;background:rgba(255,255,255,.1);
  padding:5px 11px;border-radius:9px;font-size:13px;margin-bottom:5px;}
@keyframes rise{from{opacity:0;transform:translateY(8px);}to{opacity:1;transform:none;}}
.typ .bubble{display:flex;gap:5px;align-items:center;}
.typ i{width:7px;height:7px;border-radius:50%;background:var(--muted);
  animation:bl 1.2s infinite both;}
.typ i:nth-child(2){animation-delay:.2s;}.typ i:nth-child(3){animation-delay:.4s;}
@keyframes bl{0%,80%,100%{opacity:.2;}40%{opacity:1;}}
.actions{display:flex;gap:2px;margin-top:5px;padding-left:2px;}
.ab{display:flex;align-items:center;gap:5px;background:transparent;border:0;
  color:var(--muted);cursor:pointer;padding:5px 9px;border-radius:8px;
  font-size:13px;transition:.13s;white-space:nowrap;}
.ab:hover{background:var(--act);color:var(--txt);}
.ab.ok{color:#9be29b;} .ab.playing{color:var(--acc);}
.comp{padding:12px 24px 20px;}
.pill{
max-width:760px;
margin:0 auto;

display:flex;
align-items:center;
gap:8px;

padding:10px 12px;

border-radius:45px;

/* BLUE BORDER */
border:2px solid #1d7cff;

/* GREEN INSIDE */
background:linear-gradient(
180deg,
rgba(0,255,90,.18),
rgba(0,0,0,.95)
);

/* BLUE GLOW */
box-shadow:
0 0 8px #0066ff,
0 0 18px #0066ff,
0 0 40px rgba(0,102,255,.55),

/* INNER GREEN GLOW */
inset 0 0 20px rgba(0,255,100,.28);

transition:.25s ease;
}
textarea{flex:1;resize:none;border:0;outline:0;background:transparent;color:var(--txt);
  font-size:15px;font-family:inherit;line-height:1.4;max-height:160px;
  padding:9px 4px;overflow-y:hidden;}
.ib{width:38px;height:38px;border:0;border-radius:50%;background:transparent;
  color:var(--muted);cursor:pointer;display:grid;place-items:center;
  transition:.15s;flex-shrink:0;}
.ib:hover{background:#3a3a42;color:var(--txt);} .ib.live{color:var(--acc);background:#3a2620;}
.sb{width:38px;height:38px;border:0;border-radius:13px;background:var(--acc);
box-shadow:0 0 15px #00ff88;
  color:#fff;cursor:pointer;display:grid;place-items:center;transition:.15s;flex-shrink:0;}
.sb:hover{background:var(--acc2);}
.hint{max-width:760px;margin:7px auto 0;text-align:center;color:var(--muted);font-size:12px;}
#welcome{display:flex;flex-direction:column;align-items:center;
  justify-content:center;height:100%;gap:14px;animation:rise .4s ease;}
.wv-logo{width:100px;height:100px;border-radius:50%;object-fit:cover;border:3px solid var(--bdr);}
.top-bar{display:none;align-items:center;gap:12px;padding:12px 16px;
  background:var(--side);border-bottom:1px solid var(--bdr);}
.top-bar .brand-m{font-size:18px;font-weight:700;color:var(--acc);}
.hbg{background:transparent;border:0;color:var(--txt);cursor:pointer;
  padding:4px;display:grid;place-items:center;}
.overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:90;}
@media(max-width:640px){
  .top-bar{display:flex;}
  .side{position:fixed;top:0;left:0;height:100%;z-index:100;
    transform:translateX(-100%);transition:transform .25s ease;}
  .side.open{transform:translateX(0);}
  .overlay.show{display:block;}
  .bubble{max-width:88%;}
}
/* HIDE SCROLLBAR */

::-webkit-scrollbar{
    width:0px;
    height:0px;
}

*{
    scrollbar-width:none;
}

body{
    -ms-overflow-style:none;
}
</style></head><body>

<div id="splash">
  <img class="sp-logo" src="/logo" alt="Assist Neo">
  <div class="sp-name">Assist Neo</div>
  <div class="sp-sub">Your personal AI</div>
</div>
<script>
(function(){var sp=document.getElementById('splash');
  if(sp)sp.addEventListener('animationend',function(){sp.remove();});})();
</script>

<aside class="side" id="side">
  <img class="side-logo" src="/logo" alt="logo">
  <div class="brand">ANAME</div>
  <button class="item newchat" onclick="newChat()">&#65291;&nbsp; New chat</button>
  <div class="sec">PROJECTS</div>
  <div id="projs"></div>
  <div class="sec">RECENT CHATS</div>
  <div id="chatlist"></div>
  <div class="me">
    <span class="dot"></span>UNAME
    <a href="/logout" style="color:#9aa0aa;font-size:12px;text-decoration:none;
      margin-left:auto;opacity:.6;" title="Logout">&#x2192; out</a>
  </div>
</aside>
<div class="overlay" id="overlay" onclick="closeSide()"></div>
<main class="main">
  <div class="top-bar">
    <button class="hbg" onclick="toggleSide()">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor"
        stroke-width="2" stroke-linecap="round"><path d="M3 12h18M3 6h18M3 18h18"/></svg>
    </button>
    <span class="brand-m">ANAME</span>
  </div>
  <div class="scroll" id="sc">
    <div id="welcome">
      <img class="wv-logo" src="/logo" alt="Assist Neo">
      <h2 style="font-size:22px;font-weight:600;color:var(--txt);margin:0;">Welcome, UNAME</h2>
      <p style="color:var(--muted);font-size:14px;margin:0;">How can I help you today?</p>
    </div>
    <div class="thread" id="th"></div>
  </div>
  <div class="comp" style="position:relative;">
  <div id="plusMenu" style="display:none;position:absolute;bottom:75px;left:16px;
    background:#2a2a30;border:1px solid var(--bdr);border-radius:12px;
    padding:6px;z-index:999;min-width:210px;box-shadow:0 8px 24px rgba(0,0,0,.4);">
    <button onclick="document.getElementById('fi').click();togglePlusMenu();"
      style="display:flex;align-items:center;gap:10px;width:100%;background:transparent;
      border:0;color:var(--txt);cursor:pointer;padding:10px 14px;border-radius:8px;font-size:14px;"
      onmouseenter="this.style.background='var(--act)'"
      onmouseleave="this.style.background='transparent'">
      &#128206; Upload photos &amp; files
    </button>
    <button onclick="captureScreen();togglePlusMenu();"
      style="display:flex;align-items:center;gap:10px;width:100%;background:transparent;
      border:0;color:var(--txt);cursor:pointer;padding:10px 14px;border-radius:8px;font-size:14px;"
      onmouseenter="this.style.background='var(--act)'"
      onmouseleave="this.style.background='transparent'">
      &#128247; Take screenshot
    </button>
  </div>
  <div class="pill">
    <button class="ib" id="plusBtn" onclick="togglePlusMenu()">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
        stroke-width="2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg></button>
    <textarea id="bx" rows="1" placeholder="Message ANAME..."
      oninput="grow(this)" onkeydown="key(event)"></textarea>
    <button class="ib" id="mc" onclick="mic()">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
        stroke-width="2" stroke-linecap="round">
        <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
        <path d="M19 10v2a7 7 0 0 1-14 0v-2M12 19v4"/></svg></button>
    <button class="sb" onclick="send()">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
        stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 19V5M5 12l7-7 7 7"/></svg></button>
  </div>
  <input type="file" id="fi" hidden onchange="upload()">
  <div class="hint">ANAME &middot; Enter to send</div>
</div>
</main>
<script>
const th=document.getElementById('th'),sc=document.getElementById('sc'),bx=document.getElementById('bx');
const PROJS=["General","Coding","Robotics","Image Creation"];
let cur="General",chatId=null;

const _oF=window.fetch;
window.fetch=function(...a){return _oF(...a).then(r=>{if(r.status===401)window.location='/login';return r;});};

function toggleSide(){document.getElementById('side').classList.toggle('open');document.getElementById('overlay').classList.toggle('show');}
function closeSide(){document.getElementById('side').classList.remove('open');document.getElementById('overlay').classList.remove('show');}

function renderP(){
  const c=document.getElementById('projs');c.innerHTML='';
  PROJS.forEach(p=>{const b=document.createElement('button');
    b.className='item proj'+(p===cur?' on':'');
    b.innerHTML='<span class="pd"></span>'+p;b.onclick=()=>setP(p);c.appendChild(b);});}

async function setP(p){cur=p;renderP();th.innerHTML='';chatId=null;closeSide();
  await fetch('/project',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:p})});
  greet();}
async function loadChats(){
  try{const r=await fetch('/chats');if(!r.ok)return;
    const d=await r.json();
    const c=document.getElementById('chatlist');c.innerHTML='';
    d.forEach(ch=>{
      const wrap=document.createElement('div');
      wrap.style.cssText='position:relative;display:flex;align-items:center;';
      const b=document.createElement('button');
      b.className='item chat-item'+(ch.id===chatId?' on':'');
      b.style.flex='1';
      b.innerHTML='<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg><span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">'+ch.title+'</span>';
      b.onclick=()=>{openChat(ch.id);closeSide();};
      const dot=document.createElement('button');
      dot.innerHTML='&#8942;';
      dot.style.cssText='background:transparent;border:0;color:var(--muted);cursor:pointer;padding:4px 8px;font-size:18px;border-radius:6px;flex-shrink:0;';
      dot.onmouseenter=()=>dot.style.background='var(--act)';
      dot.onmouseleave=()=>dot.style.background='transparent';
      dot.onclick=(e)=>{e.stopPropagation();showMenu(e,ch.id,ch.title);};
      wrap.appendChild(b);wrap.appendChild(dot);c.appendChild(wrap);});}catch(e){}}
async function openChat(id){
  try{const r=await fetch('/chat/'+id);const d=await r.json();
    if(d.error)return;chatId=d.id;th.innerHTML='';
    d.messages.forEach(m=>addDirect(m.text,m.role==='user'?'user':'bot'));
    loadChats();}catch(e){}}

function addDirect(text,who){
  const m=document.createElement('div');m.className='msg '+who;
  const b=document.createElement('div');b.className='bubble';b.textContent=text;
  m.appendChild(b);th.appendChild(m);addActions(m,text,who);sc.scrollTop=sc.scrollHeight;}

function addMsg(html,who){
  const m=document.createElement('div');m.className='msg '+who;
  const b=document.createElement('div');b.className='bubble';b.innerHTML=html;
  m.appendChild(b);th.appendChild(m);sc.scrollTop=sc.scrollHeight;return{m,b};}

function hideWelcome(){const w=document.getElementById('welcome');if(w)w.style.display='none';}

function stream(text,who,done){

  hideWelcome();

  const m=document.createElement('div');
  m.className='msg '+who;

  const b=document.createElement('div');
  b.className='bubble';

  m.appendChild(b);
  th.appendChild(m);

  let i=0;

  const hasMath =
      text.includes("$$") ||
      text.includes("\\(") ||
      text.includes("\\[");

  const hasImage =
      text.includes("<img");

  // INSTANT render for math/images
  if(hasMath || hasImage){

      text=text
        .split("\\\\(").join("\\(")
        .split("\\\\)").join("\\)")
        .split("\\\\[").join("\\[")
        .split("\\\\]").join("\\]");

      b.innerHTML=text;

      if(window.MathJax){

          MathJax.typesetClear([b]);

          MathJax.typesetPromise([b]);

      }

      sc.scrollTop=sc.scrollHeight;

      if(done)done(m,text);

      return;
  }

  // NORMAL typing effect
  const iv=setInterval(()=>{

    if(i<text.length){

      b.textContent+=text[i++];

      sc.scrollTop=sc.scrollHeight;

    }else{

      clearInterval(iv);

      if(done)done(m,text);

    }

  },9);

}


function typing(isImage=false){
  const t=document.createElement('div');t.className='msg bot';
  if(isImage){
    t.innerHTML=`<div class="bubble" style="background:var(--bb);padding:16px;border-radius:18px;min-width:260px;">
      <div style="font-size:13px;color:var(--muted);margin-bottom:12px;font-weight:500;">Creating image...</div>
      <div style="display:grid;grid-template-columns:repeat(12,1fr);gap:4px;">
        ${Array.from({length:120},(_,i)=>`<div style="width:6px;height:6px;border-radius:50%;background:var(--muted);opacity:${(Math.random()*0.5+0.1).toFixed(2)};animation:bl ${(Math.random()*1+0.8).toFixed(1)}s ${(Math.random()*0.5).toFixed(1)}s infinite both;"></div>`).join('')}
      </div>
      <div class="typ" style="display:flex;gap:5px;justify-content:center;margin-top:12px;"><i></i><i></i><i></i></div>
    </div>`;
  }else{
    t.innerHTML=`<div style=background:linear-gradient(
180deg,
rgba(0,255,90,.18),
rgba(0,0,0,.95)
);
      border-radius:18px;border-bottom-left-radius:5px;
      padding:12px 18px;display:inline-flex;align-items:center;gap:10px;
      box-shadow:0 2px 12px rgba(0,0,0,.25);">
      <span style="font-size:13px;color:var(--muted);letter-spacing:.3px;">Thinking</span>
      <div style="display:flex;gap:5px;align-items:center;">
        <i style="width:6px;height:6px;border-radius:50%;background:#c96442;opacity:.7;animation:bl 1.2s 0s infinite both;display:block;"></i>
        <i style="width:6px;height:6px;border-radius:50%;background:#c96442;opacity:.7;animation:bl 1.2s .2s infinite both;display:block;"></i>
        <i style="width:6px;height:6px;border-radius:50%;background:#c96442;opacity:.7;animation:bl 1.2s .4s infinite both;display:block;"></i>
      </div>
    </div>`;
  }
  th.appendChild(t);sc.scrollTop=sc.scrollHeight;return t;}
const PL='<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><polygon points="5,3 19,12 5,21"/></svg>';
const SQ='<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="4" width="16" height="16" rx="2"/></svg>';
const CP='<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>';

let currentUtt=null;
function speakOnDevice(text,btn){
  if(currentUtt){window.speechSynthesis.cancel();currentUtt=null;
    document.querySelectorAll('.ab.playing').forEach(b=>{b.classList.remove('playing');b.innerHTML=PL+' Play';});return;}
  fetch('/stop_speech',{method:'POST'});
  document.querySelectorAll('.ab.playing').forEach(b=>{b.classList.remove('playing');b.innerHTML=PL+' Play';});
  currentUtt=new SpeechSynthesisUtterance(text);currentUtt.lang='en-IN';currentUtt.rate=0.92;
  currentUtt.onend=()=>{currentUtt=null;btn.innerHTML=PL+' Play';btn.classList.remove('playing');};
  currentUtt.onerror=()=>{currentUtt=null;btn.innerHTML=PL+' Play';btn.classList.remove('playing');};
  window.speechSynthesis.speak(currentUtt);btn.classList.add('playing');btn.innerHTML=SQ+' Stop';}

const DL='<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14M5 12l7 7 7-7"/><path d="M5 19h14"/></svg>';

function addActions(m,text,who){
  const bar=document.createElement('div');bar.className='actions';
  const isImage=text==='[Generated Image]';
  if(who==='bot'&&!isImage){
    const p=document.createElement('button');p.className='ab';
    p.innerHTML=PL+' Play';p.onclick=()=>speakOnDevice(text,p);bar.appendChild(p);}
  if(who==='bot'&&isImage){
    const imgEl=m.querySelector('img');
    if(imgEl){
      const dl=document.createElement('button');dl.className='ab';
      dl.innerHTML=DL+' Download';
      dl.onclick=()=>{
        const a=document.createElement('a');
        a.href=imgEl.src;a.download='assistneo_image.png';
        a.click();};
      bar.appendChild(dl);}}
  const c=document.createElement('button');c.className='ab';c.innerHTML=CP+' Copy';
  c.onclick=()=>navigator.clipboard.writeText(text).then(()=>{
    c.innerHTML=CP+' Copied';c.classList.add('ok');
    setTimeout(()=>{c.innerHTML=CP+' Copy';c.classList.remove('ok');},2000);});
  bar.appendChild(c);m.appendChild(bar);}

function grow(t){t.style.height='auto';t.style.height=Math.min(t.scrollHeight,160)+'px';}
let plusMenuOpen=false;

function togglePlusMenu(){
  const menu=document.getElementById('plusMenu');
  plusMenuOpen=!plusMenuOpen;
  menu.style.display=plusMenuOpen?'block':'none';
  if(plusMenuOpen){
    setTimeout(()=>document.addEventListener('click',function handler(e){
      if(!document.getElementById('plusMenu').contains(e.target)&&
         e.target.id!=='plusBtn'){
        document.getElementById('plusMenu').style.display='none';
        plusMenuOpen=false;
        document.removeEventListener('click',handler);}
    }),10);}
}
let isBusy = false;

function key(e){
  if(e.key==='Enter'&&!e.shiftKey){
    e.preventDefault();
    if(!isBusy) send();
  }
}

async function send(){
  if(isBusy) return;
  isBusy=true;
  const sb=document.querySelector('.sb');
  sb.style.opacity='0.4';
  sb.style.cursor='not-allowed';
  bx.style.opacity='0.6';
  const text=bx.value.trim();if(!text){isBusy=false;sb.style.opacity='1';sb.style.cursor='pointer';bx.style.opacity='1';return;}
  const{m:um}=addMsg(text.replace(/[<>&]/g,c=>({'<':'&lt;','>':'&gt;','&':'&amp;'}[c])),'user');
  addActions(um,text,'user');bx.value='';grow(bx);
  const isImg=text.toLowerCase().includes('create')||text.toLowerCase().includes('generate')||text.toLowerCase().includes('draw');
const t=typing(isImg);
  try{const r=await fetch('/ask',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({message:text,chat_id:chatId})});
    const d=await r.json();t.remove();chatId=d.chat_id||chatId;
    if(d.reply&&d.reply.startsWith('[IMAGE]')){
      const imgUrl=d.reply.replace('[IMAGE]','').trim();
      const{m:bm}=addMsg('<img src="'+imgUrl+'" style="max-width:340px;border-radius:16px;display:block;">','bot');
      addActions(bm,'[Generated Image]','bot');
      isBusy=false;
      sb.style.opacity='1';
      sb.style.cursor='pointer';
      bx.style.opacity='1';
    }else{
      stream(d.reply||'...','bot',(m,txt)=>{
        addActions(m,txt,'bot');
        isBusy=false;
        sb.style.opacity='1';
        sb.style.cursor='pointer';
        bx.style.opacity='1';
      });
    }
    loadChats();}
  catch(e){t.remove();addMsg('(Error — check terminal)','bot');
    isBusy=false;sb.style.opacity='1';sb.style.cursor='pointer';bx.style.opacity='1';}
}
async function captureScreen(){
  const t=typing();
  try{const r=await fetch('/screenshot',{method:'POST'});const d=await r.json();t.remove();
    if(d.error){addMsg('(Screenshot failed: '+d.error+')','bot');return;}
    const html='<img src="'+d.url+'" style="max-width:240px;border-radius:12px;">';
    const{m:um}=addMsg(html,'user');addActions(um,'[Screenshot]','user');
    const t2=typing();
    const r2=await fetch('/ask',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({message:'Describe this screenshot: '+d.url,chat_id:chatId})});
    const d2=await r2.json();t2.remove();chatId=d2.chat_id||chatId;
    stream(d2.reply||'...','bot',(m,txt)=>addActions(m,txt,'bot'));loadChats();}
  catch(e){t.remove();addMsg('(Screenshot failed.)','bot');}}

async function upload(){
  const fi=document.getElementById('fi');if(!fi.files.length)return;
  const file=fi.files[0],msg=bx.value.trim();bx.value='';grow(bx);
  const isI=/[.](png|jpe?g|gif|webp|bmp)$/i.test(file.name);
  const html=(isI?'<img src="'+URL.createObjectURL(file)+'">':'')+
    '<span class="chip">&#128206; '+file.name+'</span>'+(msg?'<br>'+msg:'');
  const{m:um}=addMsg(html,'user');addActions(um,file.name+(msg?' - '+msg:''),'user');
  const t=typing();const fd=new FormData();
  fd.append('file',file);fd.append('message',msg);fd.append('chat_id',chatId||'');
  try{const r=await fetch('/upload',{method:'POST',body:fd});const d=await r.json();t.remove();
    chatId=d.chat_id||chatId;
    stream(d.reply||'...','bot',(m,txt)=>addActions(m,txt,'bot'));loadChats();}
  catch(e){t.remove();addMsg('(Upload failed.)','bot');}fi.value='';}
let activeMenu=null;

function showMenu(e,id,title){
  if(activeMenu){activeMenu.remove();activeMenu=null;return;}
  const menu=document.createElement('div');
  menu.style.cssText='position:fixed;background:#2a2a30;border:1px solid var(--bdr);border-radius:10px;padding:6px;z-index:999;min-width:140px;box-shadow:0 8px 24px rgba(0,0,0,.4);';
  menu.innerHTML=`
    <button onclick="renameChat('${id}','${title}')" style="display:flex;align-items:center;gap:8px;width:100%;background:transparent;border:0;color:var(--txt);cursor:pointer;padding:8px 12px;border-radius:7px;font-size:14px;" onmouseenter="this.style.background='var(--act)'" onmouseleave="this.style.background='transparent'">
      &#9998; Rename
    </button>
    <button onclick="deleteChat('${id}')" style="display:flex;align-items:center;gap:8px;width:100%;background:transparent;border:0;color:#f87171;cursor:pointer;padding:8px 12px;border-radius:7px;font-size:14px;" onmouseenter="this.style.background='var(--act)'" onmouseleave="this.style.background='transparent'">
      &#128465; Delete
    </button>`;
  const x=e.clientX,y=e.clientY;
  menu.style.left=Math.min(x,window.innerWidth-160)+'px';
  menu.style.top=Math.min(y,window.innerHeight-100)+'px';
  document.body.appendChild(menu);
  activeMenu=menu;
  setTimeout(()=>document.addEventListener('click',()=>{menu.remove();activeMenu=null;},{once:true}),10);}

async function renameChat(id,oldTitle){
  if(activeMenu){activeMenu.remove();activeMenu=null;}
  const newTitle=prompt('Rename chat:',oldTitle);
  if(!newTitle||newTitle===oldTitle)return;
  await fetch('/rename',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({chat_id:id,title:newTitle})});
  loadChats();}

async function deleteChat(id){
  if(activeMenu){activeMenu.remove();activeMenu=null;}
  if(!confirm('Delete this chat?'))return;
  await fetch('/delete',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({chat_id:id})});
  if(chatId===id){chatId=null;th.innerHTML='';greet();}
  loadChats();}
function newChat(){
  fetch('/new',{method:'POST'});th.innerHTML='';chatId=null;
  document.querySelectorAll('.chat-item.on').forEach(b=>b.classList.remove('on'));
  greet();}

let rec=null;
function mic(){
  const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
  if(!SR){addMsg('(Mic needs Chrome)','bot');return;}
  const btn=document.getElementById('mc');if(rec){rec.stop();return;}
  rec=new SR();rec.lang='en-IN';rec.interimResults=false;btn.classList.add('live');
  rec.onresult=e=>{bx.value=e.results[0][0].transcript;send();};
  rec.onend=()=>{btn.classList.remove('live');rec=null;};
  rec.onerror=()=>{btn.classList.remove('live');rec=null;};rec.start();}

window.addEventListener('beforeunload',()=>{window.speechSynthesis.cancel();navigator.sendBeacon('/stop_speech');});
document.addEventListener('visibilitychange',()=>{
  if(document.visibilityState==='hidden'){window.speechSynthesis.cancel();fetch('/stop_speech',{method:'POST'});}});

async function greet(){
  try{const r=await fetch('/greet');const d=await r.json();
    stream(d.reply,'bot',(m,txt)=>addActions(m,txt,'bot'));}catch(e){}}

renderP();loadChats();greet();
</script></body></html>"""

    html = html.replace("LOGO", "/logo")
    html = html.replace("ANAME", aname)
    html = html.replace("UNAME", uname)
    return html


# ── login page ───────────────────────────────────────────────────
def _login_page(err=""):
    return """<!DOCTYPE html><html><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Assist Neo &#8212; Sign in</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;}
body{background:#0a0a0a;display:flex;align-items:center;justify-content:center;
  min-height:100vh;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;}
.wrap{display:flex;width:860px;max-width:98vw;min-height:500px;border-radius:20px;
  overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,.7);}
.left{flex:1;background:linear-gradient(135deg,#0d0d2b,#1a0a3a,#0a1a3a);
  display:flex;flex-direction:column;justify-content:flex-end;padding:40px;
  position:relative;overflow:hidden;}
.left::before{content:'';position:absolute;inset:0;
  background:radial-gradient(ellipse at 60% 30%,#3a1a6e55,transparent 60%),
             radial-gradient(ellipse at 20% 80%,#1a3a6e44,transparent 50%);}
.ll{position:absolute;top:50%;left:50%;transform:translate(-50%,-60%);
  width:130px;height:130px;border-radius:50%;object-fit:cover;
  border:3px solid rgba(100,180,255,.4);box-shadow:0 0 60px rgba(60,140,255,.3);z-index:1;}
.lt{position:relative;z-index:1;}
.lt h2{color:#fff;font-size:24px;font-weight:400;line-height:1.3;}
.lt h2 b{font-weight:700;}
.right{width:400px;background:#111;display:flex;flex-direction:column;
  justify-content:center;padding:48px 40px;}
.right h1{color:#fff;font-size:26px;font-weight:600;margin-bottom:6px;}
.sub{color:#888;font-size:14px;margin-bottom:28px;}
label{color:#ccc;font-size:13px;display:block;margin-bottom:6px;}
input{width:100%;background:#1e1e1e;border:1px solid #2a2a2a;border-radius:8px;
  padding:12px 14px;font-size:15px;color:#fff;outline:none;transition:.15s;margin-bottom:18px;}
input:focus{border-color:#f0c000;}
.btn{width:100%;background:#f0c000;border:0;border-radius:8px;padding:14px;
  font-size:16px;font-weight:700;color:#000;cursor:pointer;transition:.15s;margin-top:4px;}
.btn:hover{background:#ffd000;}
.err{color:#f87171;font-size:13px;margin-bottom:14px;min-height:18px;}
.foot{text-align:center;margin-top:20px;color:#666;font-size:14px;}
.foot a{color:#f0c000;text-decoration:none;font-weight:600;}
@media(max-width:640px){.left{display:none;}.right{width:100%;padding:36px 24px;}}
</style>

<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>

</head><body>
<div class="wrap">
  <div class="left">
    <img class="ll" src="/logo" alt="Assist Neo">
    <div class="lt"><h2>Be a Part of<br><b>Something Powerful</b></h2></div>
  </div>
  <div class="right">
    <h1>Login</h1>
    <p class="sub">Enter your credentials to access your account</p>
    <div class="err" id="em">ERR</div>
    <label>Username</label>
    <input type="text" id="un" placeholder="your username" autocomplete="username">
    <label>Password</label>
    <input type="password" id="pw" placeholder="&#9679;&#9679;&#9679;&#9679;&#9679;&#9679;&#9679;&#9679;"
      autocomplete="current-password" onkeydown="if(event.key==='Enter')doLogin()">
    <button class="btn" onclick="doLogin()">Login</button>
    <div class="foot">Not a member? <a href="/register">Create an account</a></div>
  </div>
</div>
<script>
async function doLogin(){
  const un=document.getElementById('un').value.trim();
  const pw=document.getElementById('pw').value;
  const em=document.getElementById('em');em.textContent='';
  if(!un||!pw){em.textContent='Please fill in all fields.';return;}
  const r=await fetch('/login',{method:'POST',
    headers:{'Content-Type':'application/json'},body:JSON.stringify({username:un,password:pw})});
  const d=await r.json();
  if(d.ok)location.href='/';else em.textContent=d.error||'Wrong credentials.';}
</script></body></html>""".replace("ERR", err)


def _register_page(err=""):
    return """<!DOCTYPE html><html><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Assist Neo &#8212; Create Account</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;}
body{background:#0a0a0a;display:flex;align-items:center;justify-content:center;
  min-height:100vh;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;}
.wrap{display:flex;width:860px;max-width:98vw;min-height:500px;border-radius:20px;
  overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,.7);}
.left{flex:1;background:linear-gradient(135deg,#0d0d2b,#1a0a3a,#0a1a3a);
  display:flex;flex-direction:column;justify-content:flex-end;padding:40px;
  position:relative;overflow:hidden;}
.left::before{content:'';position:absolute;inset:0;
  background:radial-gradient(ellipse at 60% 30%,#3a1a6e55,transparent 60%),
             radial-gradient(ellipse at 20% 80%,#1a3a6e44,transparent 50%);}
.ll{position:absolute;top:50%;left:50%;transform:translate(-50%,-60%);
  width:130px;height:130px;border-radius:50%;object-fit:cover;
  border:3px solid rgba(100,180,255,.4);box-shadow:0 0 60px rgba(60,140,255,.3);z-index:1;}
.lt{position:relative;z-index:1;}
.lt h2{color:#fff;font-size:24px;font-weight:400;line-height:1.3;}
.lt h2 b{font-weight:700;}
.right{width:400px;background:#111;display:flex;flex-direction:column;
  justify-content:center;padding:48px 40px;}
.right h1{color:#fff;font-size:26px;font-weight:600;margin-bottom:6px;}
.sub{color:#888;font-size:14px;margin-bottom:28px;}
label{color:#ccc;font-size:13px;display:block;margin-bottom:6px;}
input{width:100%;background:#1e1e1e;border:1px solid #2a2a2a;border-radius:8px;
  padding:12px 14px;font-size:15px;color:#fff;outline:none;transition:.15s;margin-bottom:18px;}
input:focus{border-color:#f0c000;}
.btn{width:100%;background:#f0c000;border:0;border-radius:8px;padding:14px;
  font-size:16px;font-weight:700;color:#000;cursor:pointer;transition:.15s;margin-top:4px;}
.btn:hover{background:#ffd000;}
.err{color:#f87171;font-size:13px;margin-bottom:14px;min-height:18px;}
.foot{text-align:center;margin-top:20px;color:#666;font-size:14px;}
.foot a{color:#f0c000;text-decoration:none;font-weight:600;}
@media(max-width:640px){.left{display:none;}.right{width:100%;padding:36px 24px;}}
</style></head><body>
<div class="wrap">
  <div class="left">
    <img class="ll" src="/logo" alt="Assist Neo">
    <div class="lt"><h2>Join the<br><b>Assist Neo Family</b></h2></div>
  </div>
  <div class="right">
    <h1>Create Account</h1>
    <p class="sub">Set up your personal AI assistant</p>
    <div class="err" id="em">ERR</div>
    <label>Nickname <span style="color:#666;font-size:12px;">(how we call you)</span></label>
    <input type="text" id="nk" placeholder="e.g. Yuvan, Neo, Boss...">
    <label>Username <span style="color:#666;font-size:12px;">(for login)</span></label>
    <input type="text" id="un" placeholder="choose a username">
    <label>Password</label>
    <input type="password" id="pw" placeholder="&#9679;&#9679;&#9679;&#9679;&#9679;&#9679;&#9679;&#9679;"
      onkeydown="if(event.key==='Enter')doReg()">
    <button class="btn" onclick="doReg()">Create Account</button>
    <div class="foot">Already have an account? <a href="/login">Login</a></div>
  </div>
</div>
<script>
async function doReg(){
  const nk=document.getElementById('nk').value.trim();
  const un=document.getElementById('un').value.trim();
  const pw=document.getElementById('pw').value;
  const em=document.getElementById('em');em.textContent='';
  if(!un||!pw){em.textContent='Please fill in all fields.';return;}
  const r=await fetch('/register',{method:'POST',
    headers:{'Content-Type':'application/json'},body:JSON.stringify({username:un,password:pw,nickname:nk||un})});
  const d=await r.json();
  if(d.ok)location.href='/';else em.textContent=d.error||'Error.';}
</script></body></html>""".replace("ERR", err)


# ====================================================================
#  AUTH
# ====================================================================
@app.before_request
def _require_login():
    pub = {"login", "register", "serve_upload", "stop_speech_route", "serve_logo"}
    if request.endpoint in pub or (request.endpoint and "static" in request.endpoint):
        return
    if not session.get("auth"):
        if request.is_json or request.method != "GET":
            return jsonify({"error": "Login required"}), 401
        return redirect("/login")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        un = ((request.json or {}).get("username", "") if request.is_json
              else request.form.get("username", "")).strip().lower()
        pw = ((request.json or {}).get("password", "") if request.is_json
              else request.form.get("password", ""))
        users = _load_users()
        if un and un in users:
            stored = users[un]
            pw_hash = stored["pw"] if isinstance(stored, dict) else stored
            if pw_hash == _hash_pw(pw):
                nick = stored.get("nick", un.capitalize()) if isinstance(stored, dict) else un.capitalize()
                session["auth"] = True
                session["username"] = un
                session["nickname"] = nick
                session.permanent = True
                if request.is_json: return jsonify({"ok": True})
                return redirect("/")
        err = "Wrong username or password."
        if request.is_json: return jsonify({"error": err}), 401
        return _login_page(err)
    return _login_page()


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        un = ((request.json or {}).get("username", "") if request.is_json
              else request.form.get("username", "")).strip().lower()
        pw = ((request.json or {}).get("password", "") if request.is_json
              else request.form.get("password", ""))
        nick = ((request.json or {}).get("nickname", "") if request.is_json
                else request.form.get("nickname", "")).strip()
        if not nick: nick = un.capitalize()
        err = ""
        if not un or not pw:
            err = "Please fill in all fields."
        elif len(un) < 3:
            err = "Username must be at least 3 characters."
        elif len(pw) < 4:
            err = "Password must be at least 8 characters."
        else:
            users = _load_users()
            if un in users:
                err = "Username already taken."
            else:
                users[un] = {"pw": _hash_pw(pw), "nick": nick}
                _save_users(users)
                session["auth"] = True
                session["username"] = un
                session["nickname"] = nick
                session.permanent = True
                if request.is_json: return jsonify({"ok": True})
                return redirect("/")
        if request.is_json: return jsonify({"error": err}), 400
        return _register_page(err)
    return _register_page()


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# ====================================================================
#  ROUTES
# ====================================================================

@app.route("/logo")
def serve_logo():
    from flask import send_file
    import io
    logo_path = os.path.join(BASE, "assistneo_logo.png")
    if os.path.exists(logo_path):
        return send_file(logo_path, mimetype="image/png")
    # fallback: serve from embedded base64
    data = base64.b64decode(LOGO.split(",")[1])
    return send_file(io.BytesIO(data), mimetype="image/png")


@app.route("/")
def home(): return _page()


@app.route("/greet")
def greet():
    uname = _current_nick() or "there"
    hello = assistant.time_greeting()
    proj = (" You're in %s mode." % CURRENT_PROJECT) if CURRENT_PROJECT != "General" else ""
    msg = "%s, %s!%s How can I help you today?" % (hello, uname, proj)
    return jsonify({"reply": msg})


@app.route("/project", methods=["POST"])
def project():
    global CURRENT_PROJECT
    name = (request.json or {}).get("name", "General")
    if name in PROJECTS: CURRENT_PROJECT = name
    try:
        assistant._recent_turns.clear()
    except:
        pass
    return jsonify({"ok": True})


@app.route("/new", methods=["POST"])
def new():
    try:
        assistant._recent_turns.clear()
    except:
        pass
    return jsonify({"ok": True})


@app.route("/chats")
def chats(): return jsonify(list_chats())


@app.route("/chat/<cid>")
def get_chat(cid):
    d = load_chat(cid)
    return jsonify(d) if d else (jsonify({"error": "not found"}), 404)


@app.route("/uploads/<path:fn>")
def serve_upload(fn): return send_from_directory(UPLOAD_DIR, fn)


@app.route("/ask", methods=["POST"])
def ask():

    body = request.json or {}
    msg = body.get("message", "").strip()

    cid = (body.get("chat_id") or "").strip() or uuid.uuid4().hex[:12]

    if not msg:
        return jsonify({"reply": ""})

    chat = load_chat(cid) or {
        "id": cid,
        "title": "",
        "messages": []
    }

    title = chat["title"] or msg[:40]

    chat["messages"].append({
        "role": "user",
        "text": msg
    })

    with _lock:

        _capture.clear()

        try:

            short_replies = [
                "yes", "ok", "okay", "yeah",
                "sure", "continue", "go on"
            ]

            if msg.lower() in short_replies and chat["messages"]:

                previous = ""

                for m in reversed(chat["messages"][:-1]):

                    if m["role"] == "user":

                        previous = m["text"]
                        break

                msg = f"""
The user replied with: '{msg}'

Continue the previous discussion naturally.

Previous topic:
{previous}

Do NOT ask again what topic the user wants.
"""

            assistant.answer(msg)

        except Exception as e:

            _capture.append("(Error: %s)" % e)

        reply = "\n\n".join(_capture) or "..."

        if reply.startswith("[IMAGE]"):

            img_path = reply.replace("[IMAGE]", "").strip()
            img_path = img_path.replace("\\", "/")

            fname = os.path.basename(img_path)

            import shutil

            dest = os.path.join(UPLOAD_DIR, fname)

            try:
                if not os.path.exists(dest):
                    shutil.copy2(img_path, dest)
            except:
                pass

            reply = "[IMAGE]/uploads/" + fname

    chat["messages"].append({
        "role": "smith",
        "text": reply
    })

    save_chat(cid, title, chat["messages"])

    return jsonify({
        "reply": reply,
        "chat_id": cid
    })

@app.route("/screenshot", methods=["POST"])
def web_screenshot():
    import time
    try:
        from PIL import ImageGrab
        fname = "screenshot_%d.png" % int(time.time())
        path = os.path.join(UPLOAD_DIR, fname)
        ImageGrab.grab().save(path)
        return jsonify({"url": "/uploads/%s" % fname, "fname": fname})
    except ImportError:
        return jsonify({"error": "pip install pillow"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/speak", methods=["POST"])
def speak_route():
    text = (request.json or {}).get("text", "").strip()
    if text: web_speak(text)
    return jsonify({"done": True})


@app.route("/stop_speech", methods=["POST", "GET"])
def stop_speech_route():
    stop_speaking()
    return jsonify({"ok": True})


@app.route("/rename", methods=["POST"])
def rename_chat():
    body = request.json or {}
    cid = body.get("chat_id", "").strip()
    title = body.get("title", "").strip()
    if not cid or not title:
        return jsonify({"error": "missing"}), 400
    chat = load_chat(cid)
    if not chat:
        return jsonify({"error": "not found"}), 404
    chat["title"] = title
    save_chat(cid, title, chat["messages"])
    return jsonify({"ok": True})


@app.route("/delete", methods=["POST"])
def delete_chat():
    body = request.json or {}
    cid = body.get("chat_id", "").strip()
    if not cid:
        return jsonify({"error": "missing"}), 400
    path = _chat_path(cid)
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"ok": True})


@app.route("/upload", methods=["POST"])
def upload():
    f = request.files.get("file")
    msg = request.form.get("message", "").strip()
    cid = (request.form.get("chat_id") or "").strip() or uuid.uuid4().hex[:12]
    if not f: return jsonify({"reply": "No file received."})
    safe = "".join(c for c in f.filename if c.isalnum() or c in "._- ")
    path = os.path.join(UPLOAD_DIR, safe);
    f.save(path)
    ext = safe.rsplit(".", 1)[-1].lower() if "." in safe else ""
    reply = (_img_analyze(path, msg) if ext in _IMG_MIME
             else _txt_analyze(path, safe, msg) if ext in _TXT_EXTS
    else "Saved '%s'." % safe)
    chat = load_chat(cid) or {"id": cid, "title": "", "messages": []}
    title = chat["title"] or "File: %s" % safe
    chat["messages"].append({"role": "user", "text": "[File: %s] %s" % (safe, msg)})
    chat["messages"].append({"role": "smith", "text": reply})
    save_chat(cid, title, chat["messages"])
    return jsonify({"reply": reply, "chat_id": cid})


# ====================================================================
def _get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80));
        ip = s.getsockname()[0];
        s.close();
        return ip
    except:
        return "localhost"


def main():
    try:
        assistant.start_reminder_watcher()
    except:
        pass
    ip = _get_local_ip()
    threading.Timer(1.2, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    print("\n" + "=" * 56)
    print("  Assist Neo is running")
    print("  This PC   :  http://127.0.0.1:5000")
    print("  Phone/WiFi:  http://%s:5000" % ip)
    print("  Ctrl+C to stop")
    print("=" * 56 + "\n")
    app.run(host="0.0.0.0", port=5000, threaded=True)


if __name__ == "__main__":
    main()
