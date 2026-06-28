"""config/development.py — Development overrides"""
from config.base import BaseConfig


class DevelopmentConfig(BaseConfig):
    DEBUG             = True
    LOG_LEVEL         = "DEBUG"
    SESSION_COOKIE_SECURE = False      # no HTTPS locally

    # Looser rate limits for dev
    RATE_LIMIT_STREAM = 999
    RATE_LIMIT_API    = 999

    # Faster agent loop in dev
    MAX_AGENT_ITERATIONS = 5
