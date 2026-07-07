"""agents/__init__.py — Agent registry and team runner."""
from __future__ import annotations
import logging, os, time
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


# ── AI Company: each agent is an employee with a personality ────────────────
PERSONALITIES = {
    "ceo":            ("Chief Executive", "Decisive and strategic. You weigh trade-offs fast, delegate clearly, and always keep the user's actual goal in focus."),
    "planner":        ("Head of Planning", "Methodical and calm. You think in checklists and dependencies, and always state time estimates."),
    "researcher":     ("Research Lead", "Endlessly curious and rigorous. You cite sources, flag uncertainty honestly, and love surprising facts."),
    "programmer":     ("Senior Engineer", "Pragmatic craftsman. You write clean, working code first, mention edge cases, and hate over-engineering."),
    "debugger":       ("Debugging Specialist", "Patient and forensic. You reason from evidence, never guess wildly, and celebrate root causes."),
    "reviewer":       ("QA Lead", "Constructively picky. You catch what others miss and always say what is good before what is wrong."),
    "memory_manager": ("Knowledge Archivist", "Organized and precise. You keep facts tidy, cross-referenced, and retrievable."),
    "vision":         ("Vision Analyst", "Observant and exact. You describe what you actually see, measurements first, interpretation second."),
    "voice":          ("Communications Officer", "Clear and warm. You make everything easy to listen to."),
    "automation":     ("Automation Engineer", "Efficiency-obsessed. If it happens twice, you script it."),
    "browser":        ("Field Agent", "Resourceful web navigator. You get in, get the data, and report back concisely."),
    "security":       ("Security Chief", "Professionally paranoid. You think like an attacker and always mention the mitigation."),
}


class DynamicAgent(BaseAgent):
    """A specialist hired at runtime (services/dynamic_agents)."""
    def __init__(self, spec: dict, username: str = "default"):
        self.name          = spec["name"]
        self.role          = spec.get("title", spec["name"])
        self.model         = spec.get("model", "gpt-4o-mini")
        self.system_prompt = spec.get("prompt", "You are a helpful specialist.")
        self.icon          = "🧩"
        super().__init__(username=username)
        self.name = spec["name"]  # BaseAgent.__init__ may reset class attrs


def get_agent(name: str, username: str = "default") -> BaseAgent:
    cls = _REGISTRY.get(name)
    if cls is None:
        # Not a built-in: check the hired workforce, or hire on the spot
        try:
            from services import dynamic_agents
            spec = dynamic_agents.get(name)
            if spec is None:
                spec = dynamic_agents.hire(name, need="requested by CEO routing")
            if spec and not spec.get("error"):
                return DynamicAgent(spec, username=username)
        except Exception as e:
            log.debug("dynamic agent fallback: %s", e)
        cls = ResearcherAgent
    agent = cls(username=username)
    p = PERSONALITIES.get(name)
    if p:
        agent.system_prompt = (agent.system_prompt or "") + \
            "\n\nYour role in the AI Aurum company: %s. Personality: %s" % p
    return agent


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
        from services.memory_api import memory as _umem
        g = _umem.graph_walk(username, goal)
        if g:
            parts.append("Connected knowledge (graph):\n" + g)
    except Exception as e:
        log.debug("graph context unavailable: %s", e)
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

    # ── Tree-of-thought: branch strategies, reviewer picks the best ─────────
    tot_hint = ""
    if len(goal) > 80 and os.getenv("TREE_OF_THOUGHT", "1") == "1":
        try:
            from providers import AI as _AI
            yield {"status": "routing", "agent": "planner",
                   "message": "Branching strategies (tree-of-thought)..."}
            branches = _AI.generate_json(
                "Propose 3 DIFFERENT strategies to accomplish this goal. "
                'JSON: {"strategies": [{"name": "...", "approach": "1-2 '
                'sentences", "risk": "..."}]}\n\nGOAL: ' + goal,
                model="gpt-4o-mini", max_tokens=400)
            strat = branches.get("strategies", [])
            if len(strat) >= 2:
                verdict = _AI.generate_json(
                    "You are a critical reviewer. Score each strategy 1-10 for "
                    "this goal and pick a winner. JSON: {\"winner_index\": 0, "
                    "\"reason\": \"...\"}\n\nGOAL: %s\n\nSTRATEGIES: %s"
                    % (goal, str(strat)[:1500]),
                    model="gpt-4o-mini", max_tokens=150)
                wi = verdict.get("winner_index", 0)
                if isinstance(wi, int) and 0 <= wi < len(strat):
                    w = strat[wi]
                    tot_hint = ("\n\nCHOSEN STRATEGY (%s): %s"
                                % (w.get("name", "best"), w.get("approach", "")))
                    yield {"status": "plan_branch",
                           "strategies": [s.get("name", "?") for s in strat],
                           "chosen": w.get("name", "?"),
                           "reason": verdict.get("reason", "")[:150]}
        except Exception as e:
            log.debug("tree-of-thought skipped: %s", e)

    yield {"status": "routing", "agent": "ceo", "message": "CEO is routing your goal..."}
    routing = ceo.route(goal + tot_hint)
    steps   = routing.get("steps", [{"agent": "researcher", "task": goal}])
    plan    = routing.get("plan", goal)

    yield {"status": "plan", "plan": plan,
           "agents": [s.get("agent", "researcher") for s in steps]}
    bus.emit("team.started", {"username": username, "goal": goal,
                              "agents": [s.get("agent") for s in steps]}, async_=True)

    shared_ctx    = _global_context(goal, username)
    try:
        from services.experience_db import relevant_experience
        exp = relevant_experience(username, goal)
        if exp:
            shared_ctx = (shared_ctx + "\n\n" + exp).strip()
    except Exception:
        pass
    agent_outputs: list[dict] = []

    def _step_context() -> str:
        board = "\n\n".join(
            "[%s said]:\n%s" % (o["agent"].upper(), o["result"][:1500])
            for o in agent_outputs
        )
        pieces = [p for p in (shared_ctx, board) if p]
        return "\n\n".join(pieces)[:8000]

    def _speculative_providers():
        """Two healthy providers to race against each other."""
        try:
            from providers import AI as _AI
            up = [p.name for p in _AI.chain if p.available()][:2]
            return up if len(up) >= 2 else []
        except Exception:
            return []

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
        # Speculative execution: race the same task on two providers,
        # first non-error answer wins (uses the failover chain offensively)
        racers = _speculative_providers()
        result = None
        if len(racers) == 2 and os.getenv("SPECULATIVE", "1") == "1":
            def _race(prov):
                a2 = get_agent(agent_name, username)
                a2._force_provider = prov
                return a2.think(task, context=ctx)
            with ThreadPoolExecutor(max_workers=2) as rp:
                futs = {rp.submit(_race, pr): pr for pr in racers}
                for fut in as_completed(futs):
                    try:
                        r = fut.result()
                        if r and not r.startswith(("[Error", "[AI error", "[Exception")):
                            result = r
                            log.debug("speculative win: %s via %s",
                                      agent_name, futs[fut])
                            break
                    except Exception:
                        continue
        if result is None:
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

    # ── Continuous thinking: CEO self-critique + optional review round ──────
    try:
        import json as _json
        critique_raw = ceo.think(
            "You just produced this answer for the goal below. Critique it.\n"
            'Reply ONLY JSON: {"good_enough": true/false, "issue": "...", '
            '"fix_agent": "reviewer|researcher|programmer|security", "fix_task": "..."}\n\n'
            "GOAL: %s\n\nANSWER:\n%s" % (goal, final_reply[:3000]))
        import re as _re
        m = _re.search(r"\{[\s\S]*\}", critique_raw)
        verdict = _json.loads(m.group(0)) if m else {"good_enough": True}
        if not verdict.get("good_enough", True) and verdict.get("fix_task"):
            fix_agent = verdict.get("fix_agent", "reviewer")
            if fix_agent not in _REGISTRY:
                fix_agent = "reviewer"
            yield {"status": "working", "agent": fix_agent, "step": len(steps),
                   "task": "review round: " + str(verdict.get("issue", ""))[:150]}
            fixer  = get_agent(fix_agent, username)
            fix_out = fixer.think(verdict["fix_task"],
                                  context="Goal: %s\n\nDraft answer:\n%s"
                                          % (goal, final_reply[:4000]))
            agent_outputs.append({"step": len(steps), "agent": fix_agent,
                                  "task": verdict["fix_task"], "result": fix_out})
            yield {"status": "step_done", "agent": fix_agent, "step": len(steps),
                   "result": fix_out[:400]}
            final_reply = ceo.think(
                "Improve your draft answer using the %s's review. Output the final "
                "answer only.\n\nGOAL: %s\n\nDRAFT:\n%s\n\nREVIEW:\n%s"
                % (fix_agent, goal, final_reply[:4000], fix_out[:3000]))
    except Exception as e:
        log.debug("review round skipped: %s", e)

    duration    = round(time.time() - t0, 2)
    bus.emit("team.completed", {"username": username, "goal": goal,
                                "duration": duration}, async_=True)
    # agent-to-agent eval: score the final answer, log for self_improve
    _eval_overall = None
    try:
        import self_eval as _se
        _ev = _se.evaluate(goal, final_reply)
        if not _ev.get("skipped"):
            _eval_overall = _ev.get("overall")
            bus.emit("team.evaluated", {"username": username,
                     "overall": _eval_overall, "issue": _ev.get("issue", "")},
                     async_=True)
            # Reflection: failures become training data for future runs
            if _eval_overall is not None and float(_eval_overall) < 0.5:
                try:
                    from services.experience_db import _conn as _xc
                    from providers import AI as _AI2
                    lesson = _AI2.generate(
                        "This multi-agent run scored poorly (%.2f). Issue: %s. "
                        "Write ONE sentence: what to do differently next time "
                        "for goals like '%s'." % (float(_eval_overall),
                                                  _ev.get("issue", "?"), goal[:150]),
                        model="gpt-4o-mini", max_tokens=60, temperature=0.2)
                    if lesson and not lesson.startswith("[AI error"):
                        with _xc() as con:
                            con.execute(
                                "INSERT INTO experiences (username, problem, strategy, lesson) "
                                "VALUES (?,?,?,?)",
                                (username, goal[:300], "AVOID: previous attempt failed",
                                 lesson[:300]))
                except Exception:
                    pass
    except Exception:
        pass
    try:
        import threading as _th
        from services.experience_db import learn_from_run
        _th.Thread(target=learn_from_run,
                   args=(username, goal, agent_outputs, final_reply),
                   daemon=True).start()
    except Exception:
        pass
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
