"""
planning/executor.py — Streaming plan executor for SSE routes.
Yields event dicts for the SSE endpoint to forward to the client.
"""
from __future__ import annotations
import logging, time
from planning.planner import create_plan, Plan, PlanStep

log = logging.getLogger("planning.executor")


def stream_execute(goal: str, username: str = "default"):
    """
    Generator yielding SSE-compatible dicts:
      {status: "planning"}
      {plan_ready: {...}}
      {step_start: {id, agent, description}}
      {step_done:  {id, agent, result_preview}}
      {step_fail:  {id, error}}
      {verifying: True}
      {done: True, reply: "...", duration: X}
    """
    import agents as _agents

    t0 = time.time()
    yield {"status": "planning", "message": f"Understanding your goal: {goal[:60]}..."}

    plan = create_plan(goal, username)
    yield {
        "plan_ready": True,
        "understanding": plan.understanding,
        "steps": [
            {"id": s.id, "agent": s.agent, "description": s.description,
             "estimated_sec": s.estimated_sec}
            for s in plan.steps
        ],
        "total_est_sec": plan.total_est_sec,
    }

    completed_ids: set[int] = set()

    for step in plan.steps:
        if not all(d in completed_ids for d in step.depends_on):
            yield {"step_fail": {"id": step.id, "error": "Dependency not met"}}
            step.status = "failed"
            continue

        yield {"step_start": {"id": step.id, "agent": step.agent, "description": step.description}}
        step.status = "running"

        try:
            agent   = _agents.get_agent(step.agent, username)
            context = "\n".join(
                f"Step {s.id}: {s.result[:200]}"
                for s in plan.steps if s.id in completed_ids and s.result
            )
            result  = agent.think(step.description, context)
            step.result = result
            step.status = "done"
            completed_ids.add(step.id)
            yield {"step_done": {"id": step.id, "agent": step.agent,
                                  "result_preview": result[:200]}}
        except Exception as e:
            step.status = "failed"
            step.error  = str(e)
            yield {"step_fail": {"id": step.id, "error": str(e)}}

    yield {"verifying": True, "message": "Verifying and synthesising final answer..."}

    from planning.planner import _verify_and_synthesise
    final = _verify_and_synthesise(plan)
    plan.final_answer = final

    # Stream final answer
    for word in final.split():
        yield {"delta": word + " "}

    yield {
        "done":     True,
        "reply":    final,
        "plan":     plan.understanding,
        "duration": round(time.time() - t0, 2),
        "steps_completed": len(completed_ids),
        "steps_total":     len(plan.steps),
    }
