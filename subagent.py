"""
subagent.py — Parallel Sub-Agent Orchestrator for AI Aurum
===========================================================
Breaks a complex task into N isolated sub-tasks, runs each as a
separate AI call in parallel via ThreadPoolExecutor, then synthesises
all results in a final aggregation call.

Architecture:
    Task
      ↓
    [Decompose]  one AI call → list of sub-tasks
      ↓
    [Parallel Execution]  N concurrent mini-agent calls
      each: system_prompt + sub-task → mini response
      ↓
    [Synthesis]  final AI call merges all sub-results
      ↓
    yields SSE progress + final answer
"""

from __future__ import annotations
import json, logging, os
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests as _rq

log = logging.getLogger("subagent")

GITHUB_API = "https://models.inference.ai.azure.com/chat/completions"
_DEFAULT_MODEL = os.environ.get("MAIN_MODEL", "gpt-4o-mini")
MAX_SUBAGENTS  = 6  # cap to stay within rate limits


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _sse(payload: dict) -> str:
    return "data: " + json.dumps(payload) + "\n\n"


def _ai_call(messages: list, model: str, token: str,
             temperature: float = 0.5, max_tokens: int = 1000) -> str:
    """Single non-streaming AI call. Returns response text or error string."""
    try:
        resp = _rq.post(
            GITHUB_API,
            headers=_headers(token),
            json={"model": model, "messages": messages,
                  "temperature": temperature, "max_tokens": max_tokens},
            timeout=45,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        log.warning("subagent AI call failed: %s", e)
        return f"[error: {e}]"


def _decompose(task: str, model: str, token: str, n: int = 3) -> list[str]:
    """Ask the LLM to break `task` into exactly `n` parallel sub-tasks."""
    prompt = (
        f"Break the following task into exactly {n} independent sub-tasks that can be "
        f"worked on in parallel by different agents. Return ONLY a JSON array of strings — "
        f"no markdown, no explanation.\n\nTask: {task}"
    )
    raw = _ai_call(
        [{"role": "user", "content": prompt}],
        model=model, token=token, temperature=0.3, max_tokens=400,
    )
    try:
        sub_tasks = json.loads(raw)
        if isinstance(sub_tasks, list):
            return [str(s) for s in sub_tasks[:MAX_SUBAGENTS]]
    except Exception:
        pass
    # Fallback: treat as one sub-task
    return [task]


def _run_subagent(agent_id: int, sub_task: str, context: str,
                  model: str, token: str) -> tuple[int, str, str]:
    """Run a single sub-agent. Returns (agent_id, sub_task, result)."""
    system = (
        "You are a specialist sub-agent. Focus only on your assigned sub-task. "
        "Be thorough, precise, and concise. Do not repeat the task description.\n"
        + (f"\nContext from the main task:\n{context}" if context else "")
    )
    result = _ai_call(
        [{"role": "system", "content": system},
         {"role": "user",   "content": sub_task}],
        model=model, token=token, temperature=0.5, max_tokens=800,
    )
    return agent_id, sub_task, result


def _synthesise(task: str, sub_results: list[dict],
                model: str, token: str) -> str:
    """Merge sub-agent outputs into a single coherent answer."""
    results_text = "\n\n".join(
        f"Sub-agent {i+1} — {r['task']}:\n{r['result']}"
        for i, r in enumerate(sub_results)
    )
    prompt = (
        f"You are the orchestrator agent. The following is output from {len(sub_results)} "
        f"parallel sub-agents working on different aspects of a task.\n\n"
        f"Original task:\n{task}\n\n"
        f"Sub-agent results:\n{results_text}\n\n"
        f"Synthesise these into a single, well-structured final answer. "
        f"Remove redundancy, resolve contradictions, and add your own insights where needed."
    )
    return _ai_call(
        [{"role": "user", "content": prompt}],
        model=model, token=token, temperature=0.4, max_tokens=1600,
    )


def run_parallel(
    task: str,
    token: str,
    model: str | None = None,
    n_agents: int = 3,
    sub_tasks: list[str] | None = None,
) -> "Generator[str, None, None]":
    """
    Entry point. Yields SSE strings:
        {"subagent_status": "decomposing"}
        {"subagent_start":  {"id":1, "task":"..."}}
        {"subagent_done":   {"id":1, "task":"...", "result":"..."}}
        {"subagent_status": "synthesising"}
        {"delta": "..."}   (streamed final answer tokens)
        {"done": True, "n_agents": N}
    """
    if not token:
        yield _sse({"error": "⚠️ No API token — sub-agents require a GitHub Models token."})
        return

    model   = model or _DEFAULT_MODEL
    n_agents = max(1, min(n_agents, MAX_SUBAGENTS))

    # ── Step 1: Decompose (or use supplied sub-tasks) ─────────────────────────
    if not sub_tasks:
        yield _sse({"subagent_status": "decomposing",
                    "message": f"Breaking task into {n_agents} sub-tasks…"})
        sub_tasks = _decompose(task, model, token, n=n_agents)

    n_actual = len(sub_tasks)
    yield _sse({"subagent_status": "ready",
                "n_agents": n_actual,
                "sub_tasks": sub_tasks})

    # ── Step 2: Run sub-agents in parallel ────────────────────────────────────
    for i, st in enumerate(sub_tasks):
        yield _sse({"subagent_start": {"id": i + 1, "task": st}})

    sub_results: list[dict] = [None] * n_actual  # type: ignore

    with ThreadPoolExecutor(max_workers=min(n_actual, 6)) as pool:
        futures = {
            pool.submit(_run_subagent, i, sub_tasks[i], task, model, token): i
            for i in range(n_actual)
        }
        for fut in as_completed(futures):
            agent_id, sub_task, result = fut.result()
            sub_results[agent_id] = {"task": sub_task, "result": result}
            yield _sse({"subagent_done": {
                "id":     agent_id + 1,
                "task":   sub_task,
                "result": result,
            }})

    # ── Step 3: Synthesise ────────────────────────────────────────────────────
    yield _sse({"subagent_status": "synthesising",
                "message": f"Merging {n_actual} sub-agent results…"})

    final = _synthesise(task, sub_results, model, token)

    # Stream the synthesis word-by-word for a nicer UX
    words = final.split()
    chunk_size = 6
    for i in range(0, len(words), chunk_size):
        chunk = " ".join(words[i:i + chunk_size]) + " "
        yield _sse({"delta": chunk})

    yield _sse({"done": True, "n_agents": n_actual, "reply": final})
