"""config/production.py — Production overrides"""
from config.base import BaseConfig


class ProductionConfig(BaseConfig):
    DEBUG  = False
    TESTING = False
    LOG_LEVEL = "WARNING"

    SESSION_COOKIE_SECURE   = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Strict"

    # Stricter agent loop
    MAX_AGENT_ITERATIONS = 6
    TOOL_TIMEOUT_SECS    = 20

    # Stricter rate limits
    RATE_LIMIT_STREAM = 30
    RATE_LIMIT_API    = 60
