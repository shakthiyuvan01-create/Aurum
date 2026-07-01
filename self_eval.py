"""
self_eval.py — Post-response self-evaluation.
After every answer the AI briefly scores its own response for accuracy,
completeness, and helpfulness. Low scores are logged and surfaced as a
hint in the next turn's system prompt.
"""
import json
import logging
import os
import time

log = logging.getLogger("self_eval")

_EVAL_PROMPT = """You are a strict quality reviewer for an AI assistant.

User's message:
{question}

AI's response:
{response}

Rate the response on THREE dimensions (each 1-5):
- accuracy   : factually correct, no hallucinations
- completeness: addresses all parts of the question
- helpfulness : practical, actionable, well-formatted

Respond with ONLY valid JSON — no markdown:
{{"accuracy": <1-5>, "completeness": <1-5>, "helpfulness": <1-5>, "issue": "<one-sentence issue if any score < 4, else empty>"}}"""


def evaluate(question: str, response: str, model: str = None) -> dict:
    """
    Calls a fast model to score the response.
    Returns: {accuracy, completeness, helpfulness, overall, issue, skipped}
    """
    if not question or not response:
        return _skip()
    if len(response) < 20:
        return _skip()

    token  = os.getenv("GITHUB_TOKEN", "")
    if not token:
        return _skip()

    eval_model = model or os.getenv("FAST_MODEL", "gpt-4o-mini")
    prompt     = _EVAL_PROMPT.format(
        question = question[:800],
        response = response[:1200],
    )

    try:
        import requests
        r = requests.post(
            "https://models.inference.ai.azure.com/chat/completions",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "messages": [
                    {"role": "system", "content": "You are a strict AI quality reviewer. Output JSON only."},
                    {"role": "user",   "content": prompt},
                ],
                "model":      eval_model,
                "max_tokens": 120,
                "temperature": 0.0,
            },
            timeout=10,
        )
        if r.status_code != 200:
            return _skip()
        raw  = r.json()["choices"][0]["message"]["content"].strip()
        data = json.loads(raw)
        scores = {
            "accuracy":     _clamp(data.get("accuracy",    3)),
            "completeness": _clamp(data.get("completeness",3)),
            "helpfulness":  _clamp(data.get("helpfulness", 3)),
            "issue":        str(data.get("issue", "")),
            "skipped":      False,
        }
        scores["overall"] = round(
            (scores["accuracy"] + scores["completeness"] + scores["helpfulness"]) / 3, 1
        )
        log.debug("self_eval overall=%.1f issue=%r", scores["overall"], scores["issue"])
        return scores
    except Exception as e:
        log.debug("self_eval failed: %s", e)
        return _skip()


def _clamp(v) -> int:
    try:
        return max(1, min(5, int(v)))
    except Exception:
        return 3


def _skip() -> dict:
    return {"accuracy": 3, "completeness": 3, "helpfulness": 3, "overall": 3.0,
            "issue": "", "skipped": True}


def hint_for_next_turn(eval_result: dict) -> str:
    """
    Returns a system-prompt note to prepend when scores are low,
    so the AI corrects course on the next response.
    """
    if eval_result.get("skipped") or eval_result.get("overall", 5) >= 3.5:
        return ""
    issue = eval_result.get("issue", "")
    hints = []
    if eval_result.get("accuracy",    5) < 3: hints.append("be more factually precise")
    if eval_result.get("completeness",5) < 3: hints.append("address every part of the question")
    if eval_result.get("helpfulness", 5) < 3: hints.append("make the response more practical")
    note = "; ".join(hints)
    return (
        f"\n\n[SELF-EVAL NOTE] Your previous response scored "
        f"{eval_result['overall']}/5. Issues: {issue or note}. "
        "Please be more careful in this response."
    )
