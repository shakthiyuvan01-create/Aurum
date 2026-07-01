"""
debate.py — Multi-agent debate mode.
Three agents argue different perspectives; a judge synthesises the best answer.
"""
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

log = logging.getLogger("debate")

MAX_AGENTS = 3

_PERSONAS = [
    {
        "name":  "Analyst",
        "style": (
            "You are a critical, evidence-based analyst. "
            "Argue from data and facts. Be precise and cite specific examples."
        ),
    },
    {
        "name":  "Devil's Advocate",
        "style": (
            "You are a devil's advocate. Challenge assumptions, expose weaknesses, "
            "and present the strongest counter-argument possible."
        ),
    },
    {
        "name":  "Pragmatist",
        "style": (
            "You are a practical thinker. Focus on what actually works in the real world. "
            "Be direct, action-oriented, and solution-focused."
        ),
    },
]

_JUDGE_SYSTEM = """You are an impartial debate judge synthesising multiple arguments.

Your task:
1. Read all agent arguments carefully.
2. Identify the strongest points from each.
3. Construct ONE definitive, well-rounded answer.
4. Structure: brief verdict → key points → conclusion.
5. Do NOT attribute points to specific agents.
6. Be authoritative but fair."""


def _call_agent(agent_id: int, persona: dict, question: str, token: str, model: str) -> dict:
    try:
        import requests
        r = requests.post(
            "https://models.inference.ai.azure.com/chat/completions",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "messages": [
                    {"role": "system", "content": persona["style"]},
                    {"role": "user",   "content": question},
                ],
                "model":      model,
                "max_tokens": 600,
                "temperature":0.8,
            },
            timeout=45,
        )
        if r.status_code == 200:
            content = r.json()["choices"][0]["message"]["content"].strip()
            return {"id": agent_id, "name": persona["name"], "argument": content, "ok": True}
        return {"id": agent_id, "name": persona["name"], "argument": "", "ok": False}
    except Exception as e:
        log.warning("Agent %d failed: %s", agent_id, e)
        return {"id": agent_id, "name": persona["name"], "argument": "", "ok": False}


def _judge(question: str, arguments: list, token: str, model: str) -> str:
    debate_text = "\n\n".join(
        f"--- {a['name']} ---\n{a['argument']}"
        for a in arguments if a.get("ok") and a.get("argument")
    )
    if not debate_text:
        return "No valid arguments were produced."

    try:
        import requests
        r = requests.post(
            "https://models.inference.ai.azure.com/chat/completions",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "messages": [
                    {"role": "system", "content": _JUDGE_SYSTEM},
                    {"role": "user",   "content":
                        f"Question: {question}\n\n"
                        f"Agent Arguments:\n{debate_text}\n\n"
                        "Synthesise the definitive answer:"},
                ],
                "model":      model,
                "max_tokens": 1000,
                "temperature":0.3,
            },
            timeout=60,
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
        return "Judge synthesis failed — presenting best argument:\n\n" + arguments[0].get("argument", "")
    except Exception as e:
        log.error("Judge failed: %s", e)
        return arguments[0].get("argument", "") if arguments else ""


def run_debate(question: str, token: str, model: str = "gpt-4o-mini"):
    """
    Generator yielding SSE-style dicts:
      {debate_start: {agent, name}}
      {debate_arg:   {agent, name, argument}}
      {debate_judge: True}
      {done: True, reply: "...", agents: [...]}
    """
    if not token:
        yield {"error": "GITHUB_TOKEN not set"}
        return

    yield {"debate_status": "starting", "message": f"Launching {MAX_AGENTS} debate agents..."}

    arguments = [None] * MAX_AGENTS

    with ThreadPoolExecutor(max_workers=MAX_AGENTS) as pool:
        futures = {
            pool.submit(_call_agent, i, _PERSONAS[i], question, token, model): i
            for i in range(MAX_AGENTS)
        }
        for i, persona in enumerate(_PERSONAS[:MAX_AGENTS]):
            yield {"debate_start": {"agent": i, "name": persona["name"]}}

        for future in as_completed(futures):
            result = future.result()
            arguments[result["id"]] = result
            yield {"debate_arg": {
                "agent":    result["id"],
                "name":     result["name"],
                "argument": result["argument"],
                "ok":       result["ok"],
            }}

    yield {"debate_judge": True, "message": "Judge is synthesising..."}
    time.sleep(0.1)

    final = _judge(question, arguments, token, model)

    # Stream final answer word by word
    for word in final.split():
        yield {"delta": word + " "}

    yield {
        "done":    True,
        "reply":   final,
        "agents":  [
            {"id": a["id"], "name": a["name"], "argument": a["argument"]}
            for a in arguments if a
        ],
    }
