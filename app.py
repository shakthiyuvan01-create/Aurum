"""
app.py — AI Aurum Flask application
======================================
Entry point.  Run with:  python app.py
OR keep smith_web.py as the launch file (it now just imports this).

Structure
---------
services/
    auth_service.py     — password hashing, session helpers, login_required
    ai_service.py       — model routing logic
    speech_service.py   — Windows TTS / edge-tts
    chat_service.py     — chat history helpers (wraps db)
routes/
    auth.py             — /login  /register  /logout
    chat.py             — /  /ask  /greet  /project  /chats  /memory
    upload.py           — /upload/image  /uploads/<f>  /screenshot  /logo
    tools_routes.py     — /tools  /tools/run  /tools/reload  /tts  /docs  /reminders
    files.py            — /files/*  /code/run  /git/push
    settings.py         — /settings/personality
    stream_routes.py    — /stream  (SSE)
    research_routes.py  — /research  /analyze
"""
import os, threading, logging

# ── env ──────────────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(
    level   = logging.INFO,
    format  = "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
log = logging.getLogger("app")

# ── Flask ────────────────────────────────────────────────────────────────────
from flask import Flask, request, session, redirect, jsonify

import db          as _db
import vector_memory as _vmem
import assistant   as _asst
import agent       as _agent
import subagent    as _subagent
import tools       as _tools

try:
    import mistune as _mistune
    _md = _mistune.create_markdown(plugins=["strikethrough", "table", "url"])
except ImportError:
    _md = None

app = Flask(__name__)

# ── Centralised error handling ────────────────────────────────────────────────
from services.error_handler import register_error_handlers
register_error_handlers(app)

# ── dirs ─────────────────────────────────────────────────────────────────────
BASE       = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE, "uploads")
CHATS_DIR  = os.path.join(BASE, "chats")
DOCS_DIR   = os.path.join(BASE, "generated_docs")
STATIC_DIR = os.path.join(BASE, "static")
WS_DIR     = os.path.normpath(os.getenv("WORKSPACE_DIR", os.path.join(BASE, "workspace")))
for _d in (UPLOAD_DIR, CHATS_DIR, DOCS_DIR, STATIC_DIR, WS_DIR):
    os.makedirs(_d, exist_ok=True)

# ── DB + vector memory ────────────────────────────────────────────────────────
_db.init_db()
_db.migrate_json(
    os.path.join(BASE, "users.json"),
    CHATS_DIR,
    os.path.join(BASE, "neo_memory.json"),
)
_vmem.init()

# ── Activity log: persist agent/team events, task history ───────────────────
try:
    from services.activity_log import init_subscribers as _al_init
    _al_init()
except Exception as _e:
    log.warning("activity_log init failed: %s", _e)

# ── APScheduler ──────────────────────────────────────────────────────────────
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    _sched = BackgroundScheduler(daemon=True)
    _sched.start()
    from tools.scheduler_tool import set_scheduler as _set_sched
    _set_sched(_sched)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    log.info("APScheduler started")
except ImportError:
    _sched = None
    log.info("APScheduler not installed — scheduler tool disabled")

# ── Flask config ─────────────────────────────────────────────────────────────
from services.auth_service import get_secret_key
app.secret_key              = get_secret_key()
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024
app.config["PERMANENT_SESSION_LIFETIME"] = 60 * 60 * 24 * 30   # 30 days

# ── Speech wiring ─────────────────────────────────────────────────────────────
import services.speech_service as _speech
_asst.speak = _speech.speak

# ── capture (non-stream /ask) ─────────────────────────────────────────────────
_capture = []
_lock    = threading.Lock()
_tlocal  = threading.local()

def _cap(text):
    try:
        _asst._remember_turn("assistant", text)
    except Exception as _e:
        log.debug("_remember_turn failed: %s", _e)
    buf = getattr(_tlocal, "capture", None)
    (buf if buf is not None else _capture).append(text)

_asst.say = _cap

# ── Projects ──────────────────────────────────────────────────────────────────
PROJECTS = {
    "General": "",
    "Coding": (
        "You are an elite coding AI assistant like Cursor or GitHub Copilot.\n"
        "- Write complete, working code — no placeholders.\n"
        "- Use markdown code blocks with language tags.\n"
        "- When debugging, explain what was wrong AND show the fixed code.\n"
        "- When building something, give the full file.\n"
        "- After code, briefly explain what it does.\n"
        "- Detect the programming language from context.\n"
    ),
    "Robotics": "You are a robotics expert (Arduino, ESP32). Give safe, practical guidance.",
    "Image Creation": "Help create images. Interpret 'create an image of ...' as an image request.",
}
CURRENT_PROJECT = "General"
_orig_brain = _asst.ask_ai_brain


def _project_brain(q, with_context=False):
    if CURRENT_PROJECT == "Coding":
        return _asst.ask_bluesminds(q, with_context=with_context)
    ctx = PROJECTS.get(CURRENT_PROJECT, "")
    personality = (
        "You are a natural conversational AI assistant.\n"
        "Speak naturally. Be friendly. Use relevant emojis (1-3 per response).\n"
        "Do NOT ask 'Would you like to know more?' repeatedly.\n"
    )
    return _orig_brain(personality + "\n\n" + ctx + "\n\nUser: " + q, with_context)


def _set_project(name: str):
    global CURRENT_PROJECT
    if name in PROJECTS:
        CURRENT_PROJECT = name


def _current_project():
    return CURRENT_PROJECT


# ── model routing (from services) ─────────────────────────────────────────────
from services.ai_service import route_model as _route_model


# ── Before-request auth guard ─────────────────────────────────────────────────
@app.before_request
def _require_login():
    PUBLIC = {"auth.login", "auth.register", "auth.guest_login",
              "upload.serve_upload", "upload.serve_logo", "upload.serve_static"}
    ep = request.endpoint or ""
    if ep in PUBLIC or "static" in ep:
        return
    if not session.get("auth"):
        if request.is_json or request.method != "GET":
            return jsonify({"error": "Login required"}), 401
        return redirect("/login")


# ── Register blueprints ───────────────────────────────────────────────────────

# auth
from routes.auth import auth_bp, _init as _auth_init
_auth_init({"db": _db})
app.register_blueprint(auth_bp)

# chat (/ask, /chats, /memory, /, /greet, /project)
from routes.chat import chat_bp, _init as _chat_init
_chat_init({
    "db":              _db,
    "vmem":            _vmem,
    "assistant":       _asst,
    "brain":           _project_brain,
    "upload_dir":      UPLOAD_DIR,
    "set_project":     _set_project,
    "current_project": _current_project,
})
app.register_blueprint(chat_bp)

# stream (/stream SSE)
from routes.stream_routes import stream_bp, _init as _stream_init
_stream_init({
    "db":          _db,
    "vmem":        _vmem,
    "assistant":   _asst,
    "agent":       _agent,
    "route_model": _route_model,
    "save_chat":   _db.save_chat,
})
app.register_blueprint(stream_bp)

# research (/research, /analyze)
from routes.research_routes import research_bp, _init as _research_init
_research_init({"assistant": _asst})
app.register_blueprint(research_bp)

# upload (/upload/image, /uploads/<f>, /screenshot, /logo, /static)
from routes.upload import upload_bp, _init as _upload_init
_upload_init({"upload_dir": UPLOAD_DIR, "static_dir": STATIC_DIR})
app.register_blueprint(upload_bp)

# tools (/tools, /tools/run, /tools/reload, /tools/custom/save, /docs, /reminders, /tts,
#        /skills, /project)
from routes.tools_routes import tools_bp, _init as _tools_init
_tools_init({"tools": _tools, "docs_dir": DOCS_DIR, "db": _db})
app.register_blueprint(tools_bp)

# subagent (/subagent)
from routes.subagent_routes import subagent_bp, _init as _subagent_init
_subagent_init({"assistant": _asst, "subagent": _subagent})
app.register_blueprint(subagent_bp)

# files (/files/*, /code/run, /git/push)
from routes.files import files_bp, _init as _files_init
_files_init({"workspace_dir": WS_DIR, "assistant": _asst})
app.register_blueprint(files_bp)

# settings (/settings/personality)
from routes.settings import settings_bp, _init as _settings_init
_settings_init({"db": _db})
app.register_blueprint(settings_bp)

# admin (/admin/users, /admin/metrics)
from routes.admin import admin_bp, _init as _admin_init
_admin_init({"db": _db})
app.register_blueprint(admin_bp)

# debate (/debate, /debate/status)
from routes.debate_routes import debate_bp, _init as _debate_init
_debate_init({"assistant": _asst})
app.register_blueprint(debate_bp)

# agents (/agents, /agents/run, /agents/<name>/ask)
from routes.agents_routes import agents_bp, _init as _agents_init
_agents_init({"db": _db, "assistant": _asst})
app.register_blueprint(agents_bp)

# planning (/plan, /plan/preview)
from routes.planning_routes import planning_bp, _init as _planning_init
_planning_init({"db": _db})
app.register_blueprint(planning_bp)

# workflows (/workflows)
from routes.workflow_routes import workflow_bp, _init as _workflow_init
_workflow_init({"db": _db})
app.register_blueprint(workflow_bp)

# workspace / projects (/workspace/projects)
from routes.workspace_routes import workspace_bp, _init as _workspace_init
_workspace_init({"db": _db})
app.register_blueprint(workspace_bp)

# dashboard (/dashboard, /dashboard/stream)
from routes.dashboard_routes import dashboard_bp, _init as _dashboard_init
_dashboard_init({"db": _db})
app.register_blueprint(dashboard_bp)

# analytics (/analytics)
from routes.analytics_routes import analytics_bp, _init as _analytics_init
_analytics_init({"db": _db})
app.register_blueprint(analytics_bp)

# model voting (/vote)
from routes.vote_routes import vote_bp, _init as _vote_init
_vote_init({"db": _db})
app.register_blueprint(vote_bp)

# voice assistant (/voice/*)
from routes.voice_routes import voice_bp, _init as _voice_init
_voice_init({"db": _db})
app.register_blueprint(voice_bp)

# observability traces (/traces, /traces/<id>)
from routes.trace_routes import trace_bp, _init as _trace_init
_trace_init({})
app.register_blueprint(trace_bp)

# -- Flask-Limiter ----------------------------------------------------------------
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    _limiter = Limiter(
        app,
        key_func=get_remote_address,
        default_limits=["600 per hour", "60 per minute"],
        storage_uri="memory://",
    )
    log.info("Flask-Limiter active")
except ImportError:
    log.info("flask-limiter not installed -- rate limiting disabled")

# -- Session age enforcement -------------------------------------------------------
import time as _time

@app.before_request
def _enforce_session_age():
    if session.get("auth"):
        created = session.get("_created_at", 0)
        if not created:
            session["_created_at"] = _time.time()
        elif _time.time() - created > 60 * 60 * 24 * 30:
            session.clear()

# -- Auto-learning daily schedule --------------------------------------------------
if _sched:
    try:
        from services.auto_learn import run_daily_learning
        _sched.add_job(run_daily_learning, "cron", hour=3, minute=0, id="auto_learn",
                       replace_existing=True)
        log.info("Auto-learning scheduled (03:00 daily)")
        try:
            from services.self_improve import run_review as _si_run
            _sched.add_job(_si_run, "cron", day_of_week="sun", hour=4, minute=0,
                           id="self_improve", replace_existing=True)
            log.info("Self-improvement review scheduled (Sun 04:00, permission-gated)")
        except Exception as _e:
            log.warning("self_improve scheduling failed: %s", _e)
    except Exception as _ale:
        log.debug("Auto-learn schedule failed: %s", _ale)

# -- Run ---------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    log.info("Starting AI Aurum on port %d (debug=%s)", port, debug)
    app.run(host="0.0.0.0", port=port, debug=debug, threaded=True)
