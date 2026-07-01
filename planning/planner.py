"""
planning/planner.py — Autonomous task planning engine.
Goal → Understand → Plan → Estimate → Assign → Execute → Verify → Improve → Deliver
"""
from __future__ import annotations
import json, logging, os, time
from dataclasses import dataclass, asdict, field
from typing import Optional

log = logging.getLogger("planning")


@dataclass
class PlanStep:
    id:           int
    description:  str
    agent:        str          = "researcher"
    tool:         str          = ""
    depends_on:   list[int]    = field(default_factory=list)
    estimated_sec: int         = 30
    status:       str          = "pending"  # pending/running/done/failed
    result:       str          = ""
    error:        str          = ""


@dataclass
class Plan:
    goal:         str
    understanding: str
    steps:        list[PlanStep]
    total_est_sec: int
    username:     str
    created_at:   float = field(default_factory=time.time)
    status:       str   = "planned"  # planned/running/done/failed
    final_answer: str   = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["created_at"] = self.created_at
        return d


def _call_ai(prompt: str, system: str = "") -> str:
    token = os.getenv("GITHUB_TOKEN", "")
    if not token:
        return "{}"
    try:
        import requests
        r = requests.post(
            "https://models.inference.ai.azure.com/chat/completions",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system or "You are an expert task planner. Respond with valid JSON only."},
                    {"role": "user",   "content": prompt},
                ],
                "max_tokens": 1200,
                "temperature": 0.3,
            },
            timeout=45,
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        log.error("_call_ai: %s", e)
    return "{}"


def create_plan(goal: str, username: str = "default") -> Plan:
    """
    Takes a user goal and returns a Plan object with steps, agent assignments,
    time estimates, and dependencies.
    """
    prompt = f"""User goal: {goal}

Create a detailed execution plan. Return ONLY valid JSON:
{{
  "understanding": "What the user actually wants (1-2 sentences)",
  "steps": [
    {{
      "id": 1,
      "description": "Specific step description",
      "agent": "researcher|programmer|planner|reviewer|debugger|security|vision|automation|browser|memory_manager",
      "tool": "optional tool name or empty",
      "depends_on": [],
      "estimated_sec": 30
    }}
  ],
  "total_est_sec": 90
}}

Rules:
- Maximum 8 steps
- Each step must be concrete and executable
- depends_on lists step IDs that must complete first (empty = no dependency)
- estimated_sec: realistic time estimate per step
- Choose agent based on step nature"""

    raw = _call_ai(prompt)
    try:
        clean = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        data  = json.loads(clean)
    except Exception:
        data = {
            "understanding": goal,
            "steps": [{"id": 1, "description": goal, "agent": "researcher", "tool": "", "depends_on": [], "estimated_sec": 30}],
            "total_est_sec": 30,
        }

    steps = [
        PlanStep(
            id           = s.get("id", i+1),
            description  = s.get("description", ""),
            agent        = s.get("agent", "researcher"),
            tool         = s.get("tool", ""),
            depends_on   = s.get("depends_on", []),
            estimated_sec= s.get("estimated_sec", 30),
        )
        for i, s in enumerate(data.get("steps", []))
    ]

    return Plan(
        goal          = goal,
        understanding = data.get("understanding", goal),
        steps         = steps,
        total_est_sec = data.get("total_est_sec", sum(s.estimated_sec for s in steps)),
        username      = username,
    )


def execute_plan(plan: Plan) -> Plan:
    """
    Executes a plan step by step, respecting dependencies.
    Updates step statuses and results in place. Returns the plan.
    """
    import agents as _agents

    plan.status = "running"
    completed_ids: set[int] = set()

    for step in plan.steps:
        # Wait for dependencies
        if not all(d in completed_ids for d in step.depends_on):
            step.status = "failed"
            step.error  = "Dependency not met"
            continue

        step.status = "running"
        log.info("Executing step %d [%s]: %s", step.id, step.agent, step.description)

        try:
            agent   = _agents.get_agent(step.agent, plan.username)
            context = _build_context(plan, completed_ids)
            result  = agent.think(step.description, context)
            step.result = result
            step.status = "done"
            completed_ids.add(step.id)
        except Exception as e:
            step.status = "failed"
            step.error  = str(e)
            log.error("Step %d failed: %s", step.id, e)

    # Verify and synthesise
    plan.final_answer = _verify_and_synthesise(plan)
    plan.status = "done"
    return plan


def _build_context(plan: Plan, completed_ids: set) -> str:
    lines = [f"Goal: {plan.goal}"]
    for step in plan.steps:
        if step.id in completed_ids and step.result:
            lines.append(f"Step {step.id} ({step.agent}): {step.result[:300]}")
    return "\n".join(lines)


def _verify_and_synthesise(plan: Plan) -> str:
    """
    After execution: verify quality, then synthesise a final answer.
    """
    results_text = "\n\n".join(
        f"Step {s.id} [{s.agent}]: {s.result[:400]}"
        for s in plan.steps if s.status == "done" and s.result
    )

    if not results_text:
        return "No results were produced."

    verify_prompt = f"""Goal: {plan.goal}

Execution results:
{results_text}

Tasks:
1. Check if the goal was fully achieved
2. Identify anything missing or incorrect
3. Synthesise a single comprehensive final answer

If something is missing, fill the gap from your knowledge.
Output the final polished answer only — no meta-commentary."""

    return _call_ai(verify_prompt, system="You synthesise agent outputs into a final polished answer for the user.")
