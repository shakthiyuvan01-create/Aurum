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


def _global_context(goal: str, username: str) -> str:
    """Shared context automatically given to every agent in a team run:
    memory (5-tier), project context, and the current goal."""
    parts = []
    try:
        from services.memory_layers import mem
        ctx = mem.context_string(username, goal)
        if ctx:
            parts.append(ctx)
    except Exception as e:
        log.debug("memory context unavailable: %s", e)
    try:
        import db
        pc = db.get_project_context(username)
        if pc and pc.get("name"):
            parts.append("Active project: %s - %s" % (pc.get("name"), pc.get("description", "")))
    except Exception as e:
        log.debug("project context unavailable: %s", e)
    return "\n\n".join(parts)[:4000]


def run_team_stream(goal: str, username: str = "default"):
    """
    Streaming team run with agent-to-agent communication.

    - CEO routes the goal into steps.
    - Steps run IN ORDER; each agent receives the shared global context PLUS
      the outputs of every agent before it (message passing).
    - Steps the CEO marks "parallel": true run concurrently in one wave.
    - Yields event dicts as work happens (for SSE / live dashboard) and fires
      event-bus events for subscribers (memory, logs, analytics).

    Final yield: {"done": True, "reply", "plan", "agent_outputs", "duration"}
    """
    from services.event_bus import bus

    t0  = time.time()
    ceo = CeoAgent(username=username)

    yield {"status": "routing", "agent": "ceo", "message": "CEO is routing your goal..."}
    routing = ceo.route(goal)
    steps   = routing.get("steps", [{"agent": "researcher", "task": goal}])
    plan    = routing.get("plan", goal)

    yield {"status": "plan", "plan": plan,
           "agents": [s.get("agent", "researcher") for s in steps]}
    bus.emit("team.started", {"username": username, "goal": goal,
                              "agents": [s.get("agent") for s in steps]}, async_=True)

    shared_ctx    = _global_context(goal, username)
    agent_outputs: list[dict] = []

    def _step_context() -> str:
        board = "\n\n".join(
            "[%s said]:\n%s" % (o["agent"].upper(), o["result"][:1500])
            for o in agent_outputs
        )
        pieces = [p for p in (shared_ctx, board) if p]
        return "\n\n".join(pieces)[:8000]

    def _run_one(i, step):
        from services.agent_mailbox import mailbox
        agent_name = step.get("agent", "researcher")
        task       = step.get("task", goal)
        agent      = get_agent(agent_name, username)
        ctx        = _step_context()
        # Deliver any messages other agents addressed to this one
        inbox = mailbox.drain(username, agent_name)
        if inbox:
            mail = "\n".join("[Message from %s]: %s" % (m["from"], m["content"])
                              for m in inbox)
            ctx = (ctx + "\n\n" + mail).strip()
        result = agent.think(task, context=ctx)
        # Parse "@agent: note" mentions in the output and deliver them
        mailbox.deliver_mentions(username, agent_name, result, list(_REGISTRY.keys()))
        return {"step": i, "agent": agent_name, "task": task, "result": result}

    # Group consecutive parallel-marked steps into waves; default is sequential
    waves, cur = [], []
    for i, step in enumerate(steps):
        if step.get("parallel") and cur:
            cur.append((i, step))
        else:
            if cur:
                waves.append(cur)
            cur = [(i, step)]
    if cur:
        waves.append(cur)

    for wave in waves:
        for i, step in wave:
            yield {"status": "working", "agent": step.get("agent", "researcher"),
                   "step": i, "task": step.get("task", goal)[:200]}
            bus.emit("team.step.started", {"username": username,
                     "agent": step.get("agent"), "step": i}, async_=True)
        if len(wave) == 1:
            i, step = wave[0]
            try:
                out = _run_one(i, step)
            except Exception as e:
                out = {"step": i, "agent": step.get("agent", "researcher"),
                       "task": step.get("task", goal), "result": "[Error: %s]" % e}
            agent_outputs.append(out)
            yield {"status": "step_done", "agent": out["agent"], "step": out["step"],
                   "result": out["result"][:400]}
            bus.emit("team.step.completed", {"username": username,
                     "agent": out["agent"], "step": out["step"]}, async_=True)
        else:
            with ThreadPoolExecutor(max_workers=min(len(wave), 4)) as pool:
                futures = {pool.submit(_run_one, i, step): (i, step) for i, step in wave}
                for future in as_completed(futures):
                    i, step = futures[future]
                    if future.exception():
                        out = {"step": i, "agent": step.get("agent", "researcher"),
                               "task": step.get("task", goal),
                               "result": "[Error: %s]" % future.exception()}
                    else:
                        out = future.result()
                    agent_outputs.append(out)
                    yield {"status": "step_done", "agent": out["agent"],
                           "step": out["step"], "result": out["result"][:400]}
                    bus.emit("team.step.completed", {"username": username,
                             "agent": out["agent"], "step": out["step"]}, async_=True)

    agent_outputs.sort(key=lambda x: x["step"])

    yield {"status": "synthesising", "agent": "ceo"}
    synthesis_ctx = "\n\n".join(
        "[%s Step %d]\n%s" % (o["agent"].upper(), o["step"] + 1, o["result"])
        for o in agent_outputs
    )
    synthesis_prompt = (
        "Goal: %s\n\nPlan: %s\n\n"
        "All agent outputs are below. Synthesise them into one final, polished answer for the user. "
        "Be comprehensive but concise. Do not mention agent names - present as one unified response.\n\n%s"
        % (goal, plan, synthesis_ctx)
    )
    final_reply = ceo.think(synthesis_prompt)
    duration    = round(time.time() - t0, 2)
    bus.emit("team.completed", {"username": username, "goal": goal,
                                "duration": duration}, async_=True)
    try:
        from services.activity_log import record_task
        record_task(username, "team", goal,
                    detail="agents: " + ", ".join(o["agent"] for o in agent_outputs),
                    duration=duration)
    except Exception as e:
        log.debug("task history: %s", e)

    yield {"done": True, "reply": final_reply, "plan": plan, "steps": steps,
           "agent_outputs": agent_outputs, "duration": duration}


def run_team(goal: str, username: str = "default") -> dict:
    """Blocking wrapper around run_team_stream. Returns the final result dict."""
    final = {}
    for event in run_team_stream(goal, username=username):
        if event.get("done"):
            final = event
    return {
        "reply":         final.get("reply", ""),
        "plan":          final.get("plan", goal),
        "steps":         final.get("steps", []),
        "agent_outputs": final.get("agent_outputs", []),
        "duration":      final.get("duration", 0),
    }
