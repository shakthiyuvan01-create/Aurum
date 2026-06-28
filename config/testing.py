"""config/testing.py — Test overrides (in-memory DB, no TTS, etc.)"""
import os, tempfile
from config.base import BaseConfig

_TMP = tempfile.mkdtemp()


class TestingConfig(BaseConfig):
    TESTING = True
    DEBUG   = True
    SECRET_KEY = "test-secret-key-not-for-production"

    # In-memory / temp-dir storage so tests don't touch real data
    DB_PATH      = os.path.join(_TMP, "test_assistneo.db")
    METRICS_DB   = os.path.join(_TMP, "test_tool_metrics.db")
    UPLOAD_DIR   = os.path.join(_TMP, "uploads")
    DOCS_DIR     = os.path.join(_TMP, "docs")
    WORKSPACE_DIR = os.path.join(_TMP, "workspace")

    LOG_LEVEL = "ERROR"        # quieter test output
    WTF_CSRF_ENABLED = False   # no CSRF tokens in tests
    SESSION_COOKIE_SECURE = False

    # Disable external calls
    MAX_AGENT_ITERATIONS = 2
    RATE_LIMIT_STREAM = 9999
    RATE_LIMIT_API    = 9999
