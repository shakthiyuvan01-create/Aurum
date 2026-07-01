"""agents/ceo_agent.py -- CEO orchestrator: routes tasks to specialist agents.

Upgrade (Task #104): uses CapabilityRegistry.rank() for data-driven routing
instead of a hardcoded agent list in the system prompt.  The registry scores
agents by keyword + skill overlap so new agents are automatically considered.
"""
from __future__ import annotations
import json, logging
from agents.base_agent import BaseAgent

log = logging.getLogger("agents.ceo")


def _registry_context() -> str:
    """Build a compact agent list from the live capability registry."""
    try:
        from services.capability_registry import registry
        lines = []
        for cap in registry.capabilities.values():
            skills_str = ", ".join(cap.skills[:4])
            lines.append(f"- {cap.name:16s}: {cap.role}  [skills: {skills_str}]")
        return "\n".join(lines)
    except Exception:
        return ""


class CeoAgent(BaseAgent):
    name  = "ceo"
    role  = "CEO -- Orchestrator & Coordinator"
    model = "gpt-4o"
    icon  = "👔"
    tools = []

    @property
    def system_prompt(self) -> str:  # type: ignore[override]
        agent_list = _registry_context() or """- planner, researcher, programmer, debugger,
- reviewer, memory_manager, vision, voice,
- automation, browser, security"""
        return (
            "You are the CEO Agent of AI Aurum -- a master orchestrator.\n\n"
            "Your job:\n"
            "1. Understand the user's goal deeply.\n"
            "2. Decompose it into clear sub-tasks.\n"
            "3. Decide which specialist agent handles each sub-task.\n"
            "4. Synthesise all sub-results into a final polished answer.\n\n"
            f"Available specialist agents:\n{agent_list}\n\n"
            "Respond ONLY with valid JSON:\n"
            '''{"plan": "brief overall plan",\n'''
            '''  "steps": [\n'''
            '''    {"agent": "researcher", "task": "find X"},\n'''
            '''    {"agent": "programmer", "task": "code Y"}\n'''
            '''  ],\n'''
            '''  "single_agent": false}\n'''
            "If a single agent suffices, set single_agent=true and one step."
        )

    def route(self, goal: str, context: str = "") -> dict:
        """Return routing plan, preferring registry-ranked agents when GPT picks unknown names."""
        raw = self.think(goal, context)
        try:
            clean = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
            plan  = json.loads(clean)
        except Exception:
            plan  = {
                "plan":         goal,
                "steps":        [{"agent": "researcher", "task": goal}],
                "single_agent": True,
            }

        # Validate each agent name against registry; replace unknowns with best match
        try:
            from services.capability_registry import registry
            known = set(registry.capabilities.keys())
            for step in plan.get("steps", []):
                if step.get("agent") not in known:
                    best = registry.best_for(step.get("task", goal))
                    log.debug("CEO remapped unknown agent %r -> %r", step["agent"], best)
                    step["agent"] = best
        except Exception as _re:
            log.debug("Registry validation skipped: %s", _re)

        return plan
