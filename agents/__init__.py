"""agents/__init__.py — Agent registry and team runner."""
from __future__ import annotations
import logging, time
from concurrent.futures import ThreadPoolExecutor, as_completed

from agents.base_agent           import BaseAgent
from agents.ceo_agent            import CeoAgent
from agents.planner_agent        import PlannerAgent
from agents.researcher_agent     import ResearcherAgent
from agents.programmer_agent     import ProgrammerAgent
from agents.debugger_agent       import DebuggerAgent
from agents.reviewer_agent       import ReviewerAgent
from agents.memory_manager_agent import MemoryManagerAgent
from agents.vision_agent         import VisionAgent
from agents.voice_agent          import VoiceAgent
from agents.automation_agent     import AutomationAgent
from agents.browser_agent        import BrowserAgent
from agents.security_agent       import SecurityAgent

log = logging.getLogger("agents")

_REGISTRY: dict[str, type[BaseAgent]] = {
    "ceo":            CeoAgent,
    "planner":        PlannerAgent,
    "researcher":     ResearcherAgent,
    "programmer":     ProgrammerAgent,
    "debugger":       DebuggerAgent,
    "reviewer":       ReviewerAgent,
    "memory_manager": MemoryManagerAgent,
    "vision":         VisionAgent,
    "voice":          VoiceAgent,
    "automation":     AutomationAgent,
    "browser":        BrowserAgent,
    "security":       SecurityAgent,
}


def get_agent(name: str, username: str = "default") -> BaseAgent:
    cls = _REGISTRY.get(name, ResearcherAgent)
    return cls(username=username)


def list_agents() -> list[dict]:
    return [cls("").to_dict() for cls in _REGISTRY.values()]


def run_team(goal: str, username: str = "default") -> dict:
    """
    Full team run:
    1. CEO routes the goal to specialist agents
    2. Specialists run in parallel where possible
    3. CEO synthesises the final answer
    Returns: {reply, plan, steps, agent_outputs, duration}
    """
    t0 = time.time()
    ceo = CeoAgent(username=username)
    routing = ceo.route(goal)

    steps   = routing.get("steps", [{"agent": "researcher", "task": goal}])
    plan    = routing.get("plan", goal)

    agent_outputs: list[dict] = []

    # Run steps — parallel if no dependencies declared
    with ThreadPoolExecutor(max_workers=min(len(steps), 4)) as pool:
        futures = {}
        for i, step in enumerate(steps):
            agent_name = step.get("agent", "researcher")
            task       = step.get("task", goal)
            agent      = get_agent(agent_name, username)
            futures[pool.submit(agent.think, task)] = {"step": i, "agent": agent_name, "task": task}

        for future in as_completed(futures):
            meta   = futures[future]
            result = future.result() if not future.exception() else f"[Error: {future.exception()}]"
            agent_outputs.append({**meta, "result": result})

    # Sort outputs by step order
    agent_outputs.sort(key=lambda x: x["step"])

    # CEO synthesis
    synthesis_ctx = "\n\n".join(
        f"[{o['agent'].upper()} Step {o['step']+1}]\n{o['result']}"
        for o in agent_outputs
    )
    synthesis_prompt = (
        f"Goal: {goal}\n\nPlan: {plan}\n\n"
        "All agent outputs are below. Synthesise them into one final, polished answer for the user. "
        "Be comprehensive but concise. Do not mention agent names — present as one unified response.\n\n"
        + synthesis_ctx
    )
    final_reply = ceo.think(synthesis_prompt)

    return {
        "reply":         final_reply,
        "plan":          plan,
        "steps":         steps,
        "agent_outputs": agent_outputs,
        "duration":      round(time.time() - t0, 2),
    }
