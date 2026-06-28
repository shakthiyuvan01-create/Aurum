"""
config/__init__.py
==================
Usage anywhere in the app:

    from config import cfg
    print(cfg.MAIN_MODEL)
    print(cfg.MAX_AGENT_ITERATIONS)

The active config class is determined by FLASK_ENV / APP_ENV:
    development (default)  →  DevelopmentConfig
    production             →  ProductionConfig
    testing / test         →  TestingConfig
"""
import os
from config.base import BaseConfig as _Base

# Resolve active config class ─────────────────────────────────────────────────
def _get_config_class():
    env = os.getenv("FLASK_ENV", os.getenv("APP_ENV", "development")).lower()
    if env in ("production", "prod"):
        from config.production import ProductionConfig
        return ProductionConfig
    if env in ("testing", "test"):
        from config.testing import TestingConfig
        return TestingConfig
    from config.development import DevelopmentConfig
    return DevelopmentConfig


cfg: _Base = _get_config_class()
