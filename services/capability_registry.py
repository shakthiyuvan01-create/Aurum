"""
services/capability_registry.py — Skill-based agent capability registry.

Agents declare their skills as a list of descriptive strings.
The CEO queries the registry with a task description and gets back
the ranked list of agents that best match — no hardcoded names.

Usage:
    from services.capability_registry import registry

    # Auto-registers from agents package
    registry.auto_register()

    # Query best agent for a task
    best = registry.best_for("write Python code for a REST API")
    # → "programmer"

    # Get top-3 agents
    ranked = registry.rank("analyse this electrical drawing", top_n=3)
    # → [("vision", 0.91), ("security", 0.44), ("researcher", 0.38)]
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger("services.capability_registry")


@dataclass
class AgentCapability:
    name:        str
    role:        str
    skills:      list[str]        # natural-language skill descriptions
    keywords:    list[str]        # short trigger words for fast matching
    model:       str  = "gpt-4o-mini"
    icon:        str  = "🤖"
    max_tasks:   int  = 10        # concurrency limit
    priority:    int  = 50        # tie-break: higher = preferred


# ── Default capability definitions ────────────────────────────────────────────
_DEFAULT_CAPABILITIES: list[AgentCapability] = [
    AgentCapability(
        name     = "planner",
        role     = "Strategic Planner",
        model    = "gpt-4o-mini",
        icon     = "📋",
        priority = 60,
        keywords = ["plan","schedule","estimate","breakdown","timeline","roadmap","strategy","decompose","steps"],
        skills   = [
            "break goals into executable steps",
            "estimate time and effort for tasks",
            "identify task dependencies",
            "create project roadmaps",
            "flag risks and blockers",
            "assign tasks to appropriate agents",
        ],
    ),
    AgentCapability(
        name     = "researcher",
        role     = "Information Researcher",
        model    = "gemini-2.5-flash",
        icon     = "🔍",
        priority = 50,
        keywords = ["research","find","search","look up","what is","who is","when did","latest","news","fact","information"],
        skills   = [
            "web search and information retrieval",
            "fact verification from multiple sources",
            "news and current events lookup",
            "market research and competitive analysis",
            "academic and scientific research",
            "summarize long documents",
        ],
    ),
    AgentCapability(
        name     = "programmer",
        role     = "Software Programmer",
        model    = "gpt-4o",
        icon     = "💻",
        priority = 70,
        keywords = ["code","write","implement","function","class","api","script","python","javascript","debug","fix","refactor","algorithm","database","sql","html","css"],
        skills   = [
            "write complete working code in any language",
            "implement algorithms and data structures",
            "build REST APIs and web services",
            "database schema design and queries",
            "code refactoring and optimisation",
            "write unit and integration tests",
            "explain code and architecture",
        ],
    ),
    AgentCapability(
        name     = "debugger",
        role     = "Bug Diagnostician",
        model    = "gpt-4o",
        icon     = "🐛",
        priority = 65,
        keywords = ["bug","error","exception","traceback","crash","fix","broken","not working","fails","issue","problem","stack trace","TypeError","ValueError","SyntaxError"],
        skills   = [
            "diagnose runtime errors and exceptions",
            "trace bugs to their root cause",
            "fix broken code with explanation",
            "analyse stack traces",
            "identify logical errors and edge cases",
        ],
    ),
    AgentCapability(
        name     = "reviewer",
        role     = "Code Reviewer",
        model    = "gpt-4o-mini",
        icon     = "👀",
        priority = 55,
        keywords = ["review","audit","check","quality","best practice","smell","improve","feedback","critique"],
        skills   = [
            "code quality and best-practice review",
            "performance bottleneck identification",
            "readability and maintainability assessment",
            "edge case and input validation checks",
            "architecture and design pattern review",
        ],
    ),
    AgentCapability(
        name     = "memory_manager",
        role     = "Knowledge & Memory Manager",
        model    = "gpt-4o-mini",
        icon     = "🧠",
        priority = 45,
        keywords = ["remember","store","recall","knowledge","graph","entity","relation","forget","memory","learn","lesson"],
        skills   = [
            "store and retrieve long-term memories",
            "manage knowledge graph entities and relationships",
            "extract facts from conversations",
            "identify user preferences and patterns",
            "prune and consolidate stored knowledge",
        ],
    ),
    AgentCapability(
        name     = "vision",
        role     = "Visual Intelligence Agent",
        model    = "gpt-4o",
        icon     = "👁️",
        priority = 75,
        keywords = ["image","photo","picture","screenshot","diagram","drawing","chart","graph","schematic","visual","OCR","read","analyse","describe","layout","PDF diagram"],
        skills   = [
            "analyse and describe images in detail",
            "read text from screenshots and photos",
            "interpret charts, graphs, and data visualisations",
            "understand electrical schematics and engineering drawings",
            "extract tables from images",
            "compare before/after images",
            "identify objects, scenes, and anomalies",
        ],
    ),
    AgentCapability(
        name     = "voice",
        role     = "Voice Interface Agent",
        model    = "gpt-4o-mini",
        icon     = "🎙️",
        priority = 40,
        keywords = ["speak","listen","voice","audio","speech","tts","stt","transcribe","say","read aloud","multilingual"],
        skills   = [
            "convert speech to text (STT)",
            "convert text to speech (TTS)",
            "handle multilingual voice conversations",
            "manage wake word detection",
        ],
    ),
    AgentCapability(
        name     = "automation",
        role     = "Automation & Workflow Agent",
        model    = "gpt-4o-mini",
        icon     = "⚙️",
        priority = 55,
        keywords = ["automate","schedule","workflow","cron","trigger","repeat","notify","send","email","telegram","slack","every day","morning","weekly"],
        skills   = [
            "design and execute multi-step workflows",
            "schedule recurring automated tasks",
            "send notifications via Telegram, email, Slack",
            "chain multiple tools and services",
            "monitor conditions and trigger actions",
        ],
    ),
    AgentCapability(
        name     = "browser",
        role     = "Web Browser Agent",
        model    = "gpt-4o-mini",
        icon     = "🌐",
        priority = 60,
        keywords = ["browse","navigate","website","url","scrape","click","form","login","download","table","web page","extract","compare sites"],
        skills   = [
            "navigate and scrape web pages",
            "fill and submit web forms",
            "extract tables and structured data from websites",
            "compare content across multiple URLs",
            "download files from the web",
        ],
    ),
    AgentCapability(
        name     = "security",
        role     = "Security Analyst",
        model    = "gpt-4o",
        icon     = "🔒",
        priority = 70,
        keywords = ["security","vulnerability","injection","xss","csrf","auth","password","exploit","threat","pentest","audit","safe","risk"],
        skills   = [
            "identify SQL injection and XSS vulnerabilities",
            "review authentication and authorisation logic",
            "detect hardcoded secrets and credentials",
            "assess CSRF and session security",
            "provide security fixes with explanation",
        ],
    ),
]


class CapabilityRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, AgentCapability] = {}

    def register(self, cap: AgentCapability) -> None:
        self._agents[cap.name] = cap
        log.debug("Registered agent '%s' with %d skills", cap.name, len(cap.skills))

    def auto_register(self) -> int:
        """Register all default capabilities. Call once at startup."""
        for cap in _DEFAULT_CAPABILITIES:
            self.register(cap)
        return len(self._agents)

    def get(self, name: str) -> Optional[AgentCapability]:
        return self._agents.get(name)

    def list_all(self) -> list[dict]:
        return [
            {
                "name":     c.name,
                "role":     c.role,
                "model":    c.model,
                "icon":     c.icon,
                "skills":   c.skills,
                "keywords": c.keywords,
                "priority": c.priority,
            }
            for c in sorted(self._agents.values(), key=lambda x: -x.priority)
        ]

    def rank(self, task: str, top_n: int = 3) -> list[tuple[str, float]]:
        """
        Score every agent against the task description.
        Returns [(agent_name, score), ...] sorted by score descending.

        Scoring:
          - Keyword match in task: +2.0 per keyword
          - Skill phrase overlap (word-level): +1.0 per matching word
          - Priority tie-break: +0.001 * priority
        """
        task_lower   = task.lower()
        task_words   = set(re.findall(r"\w+", task_lower))
        scores: dict[str, float] = {}

        for name, cap in self._agents.items():
            score = 0.0
            # Keyword match
            for kw in cap.keywords:
                if kw.lower() in task_lower:
                    score += 2.0

            # Skill phrase word overlap
            for skill in cap.skills:
                skill_words = set(re.findall(r"\w+", skill.lower()))
                overlap     = len(skill_words & task_words)
                score      += overlap * 0.5

            # Priority tie-break
            score += cap.priority * 0.001

            scores[name] = round(score, 3)

        ranked = sorted(scores.items(), key=lambda x: -x[1])
        return ranked[:top_n]

    def best_for(self, task: str) -> str:
        """Return the single best agent name for a task."""
        ranked = self.rank(task, top_n=1)
        return ranked[0][0] if ranked else "researcher"

    def agents_for_skills(self, required_skills: list[str]) -> list[str]:
        """Find agents that cover ALL required skills (any keyword match)."""
        results = []
        for name, cap in self._agents.items():
            all_skills_lower = " ".join(cap.skills + cap.keywords).lower()
            if all(
                any(word in all_skills_lower for word in req.lower().split())
                for req in required_skills
            ):
                results.append(name)
        return results


# ── Singleton ─────────────────────────────────────────────────────────────────
registry = CapabilityRegistry()
registry.auto_register()
