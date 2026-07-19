"""Skills framework — pluggable skill execution and management.

Port of Hermes' skills system adapted for Aurum.
Skills are self-contained capabilities that can be loaded, managed, and executed.
"""
from __future__ import annotations

import importlib
import logging
import os
import pkgutil
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class Skill:
    """A single skill with name, description, and execute function."""

    def __init__(self, name: str, description: str, execute: Optional[Callable] = None,
                 category: str = "general", enabled: bool = True):
        self.name = name
        self.description = description
        self.execute = execute
        self.category = category
        self.enabled = enabled

    def __repr__(self):
        return f"Skill({self.name}, cat={self.category}, enabled={self.enabled})"


class SkillsRegistry:
    """Registry for all loaded skills."""

    def __init__(self):
        self._skills: Dict[str, Skill] = {}
        self._categories: Dict[str, List[Skill]] = {}

    def register(self, skill: Skill) -> None:
        self._skills[skill.name] = skill
        self._categories.setdefault(skill.category, []).append(skill)
        logger.debug("Registered skill '%s' in category '%s'", skill.name, skill.category)

    def unregister(self, name: str) -> None:
        skill = self._skills.pop(name, None)
        if skill:
            cat = self._categories.get(skill.category, [])
            if skill in cat:
                cat.remove(skill)

    def get(self, name: str) -> Optional[Skill]:
        return self._skills.get(name)

    def list(self, category: Optional[str] = None) -> List[Skill]:
        if category:
            return self._categories.get(category, [])
        return list(self._skills.values())

    def categories(self) -> List[str]:
        return list(self._categories.keys())

    def execute(self, name: str, **kwargs) -> Any:
        skill = self.get(name)
        if not skill:
            raise KeyError(f"Skill '{name}' not found")
        if not skill.enabled:
            raise RuntimeError(f"Skill '{name}' is disabled")
        if not skill.execute:
            raise RuntimeError(f"Skill '{name}' has no execute function")
        return skill.execute(**kwargs)


# Global registry
_registry = SkillsRegistry()


def get_registry() -> SkillsRegistry:
    return _registry


def register_skill(skill: Skill) -> None:
    _registry.register(skill)


def discover_skills(skills_dir: Optional[str] = None) -> int:
    """Auto-discover skills from the skills directory."""
    if skills_dir is None:
        skills_dir = os.path.dirname(os.path.abspath(__file__))

    count = 0
    for entry in os.scandir(skills_dir):
        if entry.is_dir() and not entry.name.startswith("_"):
            # Check for __init__.py or skill.py
            init_file = os.path.join(entry.path, "__init__.py")
            skill_file = os.path.join(entry.path, "skill.py")
            load_path = None
            if os.path.exists(init_file):
                load_path = init_file
            elif os.path.exists(skill_file):
                load_path = skill_file

            if load_path:
                try:
                    spec = importlib.util.spec_from_file_location(
                        f"skills.{entry.name}", load_path
                    )
                    if spec and spec.loader:
                        mod = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(mod)
                        if hasattr(mod, "register_skill"):
                            mod.register_skill(_registry)
                            count += 1
                except Exception as e:
                    logger.warning("Failed to load skill '%s': %s", entry.name, e)

    return count
