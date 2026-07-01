"""
services/model_voting.py — Multi-model consensus voting.
Asks GPT-4o + Gemini + Claude + Llama simultaneously.
Votes / merges for the best answer. SSE-friendly generator.
"""
from __future__ import annotations
import json, logging, os, time
from concurrent.futures import ThreadPoolExecutor, as_completed

log = logging.getLogger("services.model_voting")

_MODELS = [
    {"id": "gpt-4o",           "label": "GPT-4o",       "backend": "github"},
    {"id": "gpt-4o-mini",      "label": "GPT-4o-mini",  "backend": "github"},
    {"id": "gemini-2.5-flash", "label": "Gemini Flash",  "backend": "gemini"},
]
# Add Ollama if available
try:
    from services.ollama_service import is_available, list_models
    if is_available():
        for m in list_models()[:1]:
            _MODELS.append({"id": m, "label": f"Ollama/{m}", "backend": "ollama"})
except Exception:
    pass


def _call_github(model_id: str, prompt: str, system: str) -> str:
    token = os.getenv("GITHUB_TOKEN","")
    if not token: return ""
    try:
        import requests
        msgs = [{"role":"user","content":prompt}]
        if system: msgs.insert(0,{"role":"system","content":system})
        r = requests.post(
            "https://models.inference.ai.azure.com/chat/completions",
            headers={"Authorization":f"Bearer {token}","Content-Type":"application/json"},
            json={"model":model_id,"messages":msgs,"max_tokens":800,"temperature":0.5},
            timeout=60,
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        log.warning("%s error: %s", model_id, e)
    return ""


def _call_gemini(model_id: str, prompt: str) -> str:
    key = os.getenv("GEMINI_API_KEY","")
    if not key: return ""
    try:
        from google import genai
        client = genai.Client(api_key=key)
        r = client.models.generate_content(model=model_id, contents=prompt)
        return r.text.strip() if r.text else ""
    except Exception as e:
        log.warning("Gemini error: %s", e)
    return ""


def _call_ollama(model_id: str, prompt: str) -> str:
    from services.ollama_service import chat
    return chat(prompt, model=model_id)


def _ask_model(m: dict, prompt: str, system: str) -> dict:
    t0 = time.time()
    try:
        if m["backend"] == "github":
            answer = _call_github(m["id"], prompt, system)
        elif m["backend"] == "gemini":
            answer = _call_gemini(m["id"], prompt)
        elif m["backend"] == "ollama":
            answer = _call_ollama(m["id"], prompt)
        else:
            answer = ""
    except Exception as e:
        answer = ""
        log.warning("Model %s exception: %s", m["id"], e)
    return {
        "model":    m["label"],
        "answer":   answer,
        "latency":  round(time.time() - t0, 2),
        "ok":       bool(answer),
    }


def _synthesise(question: str, answers: list[dict]) -> str:
    """Judge: pick best answer or synthesise from all."""
    valid = [a for a in answers if a.get("ok") and a.get("answer")]
    if not valid:
        return "No model produced a valid answer."
    if len(valid) == 1:
        return valid[0]["answer"]

    combined = "\n\n".join(f"[{a['model']}]\n{a['answer']}" for a in valid)
    token = os.getenv("GITHUB_TOKEN","")
    if not token:
        # Just return best answer (longest)
        return max(valid, key=lambda x: len(x["answer"]))["answer"]

    import requests
    r = requests.post(
        "https://models.inference.ai.azure.com/chat/completions",
        headers={"Authorization":f"Bearer {token}","Content-Type":"application/json"},
        json={
            "model": "gpt-4o-mini",
            "messages": [
                {"role":"system","content":"You synthesise multiple AI answers into one optimal final answer. Be concise and accurate."},
                {"role":"user","content":f"Question: {question}\n\nModel answers:\n{combined}\n\nSynthesize the best final answer:"},
            ],
            "max_tokens": 800,
            "temperature": 0.2,
        },
        timeout=30,
    )
    if r.status_code == 200:
        return r.json()["choices"][0]["message"]["content"].strip()
    return valid[0]["answer"]


def vote(question: str, system: str = "") -> dict:
    """
    Parallel multi-model query + synthesis.
    Returns: {answers: [...], synthesis: str, best_model: str, duration: float}
    """
    t0 = time.time()
    answers = []
    with ThreadPoolExecutor(max_workers=len(_MODELS)) as pool:
        futures = {pool.submit(_ask_model, m, question, system): m for m in _MODELS}
        for future in as_completed(futures):
            answers.append(future.result())

    synthesis  = _synthesise(question, answers)
    best_model = max((a for a in answers if a["ok"]), key=lambda x: len(x["answer"]), default={}).get("model","")
    return {
        "answers":    answers,
        "synthesis":  synthesis,
        "best_model": best_model,
        "duration":   round(time.time() - t0, 2),
    }


def vote_stream(question: str, system: str = ""):
    """Generator for SSE: yields model answers as they arrive, then synthesis."""
    t0 = time.time()
    answers = []
    with ThreadPoolExecutor(max_workers=len(_MODELS)) as pool:
        futures = {pool.submit(_ask_model, m, question, system): m for m in _MODELS}
        yield {"status": "voting", "models": [m["label"] for m in _MODELS]}
        for future in as_completed(futures):
            result = future.result()
            answers.append(result)
            yield {"model_answer": result}
    yield {"synthesising": True}
    synthesis = _synthesise(question, answers)
    for word in synthesis.split():
        yield {"delta": word + " "}
    yield {"done": True, "synthesis": synthesis, "answers": answers,
           "duration": round(time.time()-t0, 2)}
