"""
config/base.py — Base configuration for Assist Neo
All settings live here with safe defaults.
Override in development.py / production.py or via environment variables.
"""
import os

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class BaseConfig:
    # ── Flask ─────────────────────────────────────────────────────────────────
    DEBUG   = False
    TESTING = False
    SECRET_KEY: str | None = None          # filled at runtime from .secret_key / env

    MAX_CONTENT_LENGTH         = 32 * 1024 * 1024   # 32 MB upload limit
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 30  # 30-day sessions
    SESSION_COOKIE_HTTPONLY    = True
    SESSION_COOKIE_SAMESITE    = "Lax"

    # ── Paths ─────────────────────────────────────────────────────────────────
    # On Render.com the persistent disk is mounted at /data — use it when available
    _DATA        = os.getenv("RENDER_DATA_DIR", _BASE)   # /data on Render, _BASE locally
    BASE_DIR     = _BASE
    UPLOAD_DIR   = os.path.join(_DATA, "uploads")
    CHATS_DIR    = os.path.join(_DATA, "chats")
    DOCS_DIR     = os.path.join(_DATA, "generated_docs")
    STATIC_DIR   = os.path.join(_BASE, "static")
    WORKSPACE_DIR = os.path.normpath(
        os.getenv("WORKSPACE_DIR", os.path.join(_DATA, "workspace"))
    )

    # ── Database ──────────────────────────────────────────────────────────────
    DB_PATH      = os.path.join(_DATA, "aiaurum.db")
    METRICS_DB   = os.path.join(_DATA, "tool_metrics.db")

    # ── AI / Model settings ───────────────────────────────────────────────────
    MAIN_MODEL   = os.getenv("MAIN_MODEL",   "gpt-4o-mini")
    FAST_MODEL   = os.getenv("FAST_MODEL",   "gpt-3.5-turbo")
    CODE_MODEL   = os.getenv("CODE_MODEL",   "gpt-4o")
    OLLAMA_URL   = os.getenv("OLLAMA_URL",   "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

    # ── API Keys ──────────────────────────────────────────────────────────────
    GITHUB_TOKEN       = os.getenv("GITHUB_TOKEN", "")
    GEMINI_API_KEY     = os.getenv("GEMINI_API_KEY", "")
    OPENAI_API_KEY     = os.getenv("OPENAI_API_KEY", "")
    ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
    ELEVENLABS_VOICE   = os.getenv("ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL")
    WEATHER_API_KEY    = os.getenv("WEATHER_API_KEY", "")

    # ── Tool / agent settings ─────────────────────────────────────────────────
    MAX_AGENT_ITERATIONS = int(os.getenv("MAX_AGENT_ITERATIONS", "8"))
    TOOL_TIMEOUT_SECS    = int(os.getenv("TOOL_TIMEOUT_SECS",    "30"))
    CONCURRENT_TOOLS_MAX = int(os.getenv("CONCURRENT_TOOLS_MAX", "8"))
    TOOL_WARN_FAILURES   = int(os.getenv("TOOL_WARN_FAILURES",   "3"))
    TOOL_WARN_WINDOW     = int(os.getenv("TOOL_WARN_WINDOW",     "3600"))

    # ── Speed / latency settings ──────────────────────────────────────────────
    # Plan-phase token budget (tool decisions only, not the final answer)
    PLAN_MAX_TOKENS      = int(os.getenv("PLAN_MAX_TOKENS",      "600"))
    # Temperature for the plan call (lower = faster, more deterministic)
    PLAN_TEMPERATURE     = float(os.getenv("PLAN_TEMPERATURE",   "0.3"))
    # Temperature for the streaming answer call
    ANSWER_TEMPERATURE   = float(os.getenv("ANSWER_TEMPERATURE", "0.6"))
    # How many history turns to send (fewer = fewer tokens per request)
    HISTORY_TURNS        = int(os.getenv("HISTORY_TURNS",        "6"))
    # Semantic memory retrieval count (n=2 is fast; increase for deeper recall)
    MEMORY_RETRIEVE_N    = int(os.getenv("MEMORY_RETRIEVE_N",    "2"))
    # Minimum message length before semantic memory search kicks in
    MEMORY_MIN_MSG_LEN   = int(os.getenv("MEMORY_MIN_MSG_LEN",   "40"))
    # API request timeouts
    API_TIMEOUT_SECS     = int(os.getenv("API_TIMEOUT_SECS",     "45"))
    OLLAMA_TIMEOUT_SECS  = int(os.getenv("OLLAMA_TIMEOUT_SECS",  "60"))
    # Fast-model threshold: msgs under this char count go to FAST_MODEL
    FAST_MODEL_THRESHOLD = int(os.getenv("FAST_MODEL_THRESHOLD", "300"))

    # ── Memory ────────────────────────────────────────────────────────────────
    SIMILARITY_THRESHOLD  = float(os.getenv("SIMILARITY_THRESHOLD",  "0.30"))
    RECENCY_HALF_LIFE     = int(  os.getenv("RECENCY_HALF_LIFE",      str(7 * 24 * 3600)))
    MEMORY_TOP_K          = int(  os.getenv("MEMORY_TOP_K",           "5"))

    # ── Logging ───────────────────────────────────────────────────────────────
    LOG_LEVEL  = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"

    # ── Rate limiting (requests per minute per user) ──────────────────────────
    RATE_LIMIT_STREAM  = int(os.getenv("RATE_LIMIT_STREAM",  "60"))
  