"""Skills management tool — list, enable, disable, execute skills."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from skills import SkillsRegistry, get_registry, register_skill, Skill, discover_skills

logger = logging.getLogger(__name__)


def list_skills(category: Optional[str] = None) -> List[Dict[str, Any]]:
    """List all registered skills."""
    registry = get_registry()
    skills = registry.list(category)
    return [
        {
            "name": s.name,
            "description": s.description,
            "category": s.category,
            "enabled": s.enabled,
        }
        for s in skills
    ]


def list_categories() -> List[str]:
    return get_registry().categories()


def run_skill(name: str, **kwargs) -> Any:
    """Execute a skill by name."""
    return get_registry().execute(name, **kwargs)


def refresh_skills():
    """Re-discover skills from the skills directory."""
    count = discover_skills()
    logger.info("Discovered %d skills", count)
    return count
