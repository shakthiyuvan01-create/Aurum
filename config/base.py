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
    BASE_DIR    = _BASE
    UPLOAD_DIR  = os.path.join(_BASE, "uploads")
    CHATS_DIR   = os.path.join(_BASE, "chats")
    DOCS_DIR    = os.path.join(_BASE, "generated_docs")
    STATIC_DIR  = os.path.join(_BASE, "static")
    WORKSPACE_DIR = os.path.normpath(
        os.getenv("WORKSPACE_DIR", os.path.join(_BASE, "workspace"))
    )

    # ── Database ──────────────────────────────────────────────────────────────
    DB_PATH      = os.path.join(_BASE, "assistneo.db")
    METRICS_DB   = os.path.join(_BASE, "tool_metrics.db")

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

    # ── Memory ────────────────────────────────────────────────────────────────
    SIMILARITY_THRESHOLD  = float(os.getenv("SIMILARITY_THRESHOLD",  "0.30"))
    RECENCY_HALF_LIFE     = int(  os.getenv("RECENCY_HALF_LIFE",      str(7 * 24 * 3600)))
    MEMORY_TOP_K          = int(  os.getenv("MEMORY_TOP_K",           "5"))

    # ── Logging ───────────────────────────────────────────────────────────────
    LOG_LEVEL  = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"

    # ── Rate limiting (requests per minute per user) ──────────────────────────
    RATE_LIMIT_STREAM  = int(os.getenv("RATE_LIMIT_STREAM",  "60"))
    RATE_LIMIT_API     = int(os.getenv("RATE_LIMIT_API",     "120"))

    # ── Permissions ───────────────────────────────────────────────────────────
    DEFAULT_ROLE       = "user"       # role assigned on registration
    ADMIN_USERNAMES    = set(         # bootstrap admins (comma-separated env)
        u.strip() for u in os.getenv("ADMIN_USERNAMES", "admin").split(",") if u.strip()
    )

    @classmethod
    def from_env(cls) -> "BaseConfig":
        """Return the correct config class based on FLASK_ENV / APP_ENV."""
        env = os.getenv("FLASK_ENV", os.getenv("APP_ENV", "development")).lower()
        mapping = {
            "production": "config.production.ProductionConfig",
            "prod":       "config.production.ProductionConfig",
            "testing":    "config.testing.TestingConfig",
            "test":       "config.testing.TestingConfig",
        }
        if env in mapping:
            module_path, cls_name = mapping[env].rsplit(".", 1)
            import importlib
            mod = importlib.import_module(module_path)
            return getattr(mod, cls_name)
        # default: development
        from config.development import DevelopmentConfig
        return DevelopmentConfig
