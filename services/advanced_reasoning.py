"""services/advanced_reasoning.py - Chain-of-thought, ToT, reflection, self-checking, long-term planning"""
from __future__ import annotations
import json, logging, os, re, time
from typing import Any, Dict, List, Optional
log = logging.getLogger("services.advanced_reasoning")

def chain_of_thought(question: str, context: str = "", steps: int = 3) -> Dict[str, Any]:
    """Break a complex question into reasoning steps."""
    from providers import AI
    prompt = f"""Break down this question step by step. Show your reasoning for each step.
Question: {question}
Context: {context if context else 'None'}
Think step by step, then give your final answer.
Format:
## Step 1: ...
## Step 2: ...
...
## Final Answer: ..."""
    result = AI.generate(prompt, max_tokens=1500, temperature=0.3)
    steps_list = []
    for line in (result or "").split("\n"):
        if re.match(r"## Step \d+:", line):
            steps_list.append(line.strip())
    return {"question": question, "full_reasoning": result or "", "steps": steps_list, "step_count": len(steps_list)}

def tree_of_thought(question: str, branches: int = 3, depth: int = 2) -> Dict[str, Any]:
    """Explore multiple reasoning paths and pick the best."""
    from providers import AI
    paths = []
    for i in range(branches):
        result = AI.generate(
            f"Explore reasoning path {i+1} for: {question}\nThink differently from other paths. Be creative.",
            max_tokens=600, temperature=0.8)
        paths.append({"path": i+1, "reasoning": result or ""})
    # Evaluate paths
    eval_prompt = f"Question: {question}\n\nPaths:\n" + "\n".join(f"Path {p['path']}: {p['reasoning'][:300]}" for p in paths)
    eval_result = AI.generate(
        eval_prompt + "\n\nWhich path is most correct and why? Output path number and reasoning.",
        max_tokens=400, temperature=0.2)
    best = 1
    m = re.search(r"Path (\d+)", eval_result or "")
    if m: best = int(m.group(1))
    return {"question": question, "paths": paths, "best_path": best, "evaluation": eval_result or ""}

def reflect_on_answer(question: str, answer: str) -> Dict[str, Any]:
    """Self-reflection: critique and improve an answer."""
    from providers import AI
    critique = AI.generate(
        f"Critique this answer. What's missing, wrong, or could be improved?\nQ: {question}\nA: {answer}\nBe specific and harsh.",
        max_tokens=500, temperature=0.3)
    improved = AI.generate(
        f"Based on this critique, write an improved answer:\nQ: {question}\nOriginal: {answer}\nCritique: {critique}\nImproved answer:",
        max_tokens=1000, temperature=0.2)
    return {
        "question": question, "original_answer": answer,
        "critique": critique or "", "improved_answer": improved or "",
    }

def self_check(answer: str, facts: List[str] = None) -> Dict[str, Any]:
    """Verify an answer for accuracy, consistency, and completeness."""
    from providers import AI
    checks = []
    for criterion in ["accuracy", "consistency", "completeness", "clarity"]:
        result = AI.generate(
            f"Rate this answer on {criterion} (pass/fail). Be strict.\nAnswer: {answer}\n\nOutput: pass|fail and one sentence why.",
            max_tokens=150, temperature=0.1)
        passed = (result or "").lower().startswith("pass")
        checks.append({"criterion": criterion, "passed": passed, "reason": (result or "")[:200]})
    fact_checks = []
    if facts:
        for fact in facts:
            result = AI.generate(
                f"Does this answer contradict the established fact?\nFact: {fact}\nAnswer: {answer}\nOutput: consistent|contradicts|unrelated and why.",
                max_tokens=100, temperature=0.1)
            fact_checks.append({"fact": fact, "verdict": (result or "")[:150]})
    return {"checks": checks, "fact_checks": fact_checks, "all_passed": all(c["passed"] for c in checks)}

def long_term_plan(goal: str, context: str = "") -> Dict[str, Any]:
    """Generate a long-term plan with milestones and timelines."""
    from providers import AI
    result = AI.generate(
        f"Create a detailed long-term plan for: {goal}\nContext: {context if context else 'None'}\n"
        f"Include: milestones, timeline, resources needed, risks, success criteria.\n"
        f"Format as structured markdown with ## sections.",
        max_tokens=1500, temperature=0.3)
    return {"goal": goal, "plan": result or ""}

def multi_model_routing(question: str, models: List[str] = None) -> Dict[str, Any]:
    """Query multiple models and compare responses."""
    if not models:
        models = ["gpt-4o-mini", "gpt-4o"]
    responses = []
    for model in models:
        try:
            from providers import AI
            r = AI.generate(question, model=model, max_tokens=500, temperature=0.2)
            responses.append({"model": model, "response": (r or "")[:500]})
        except Exception as e:
            responses.append({"model": model, "error": str(e)})
    # Synthesize best answer
    from providers import AI
    synthesis = AI.generate(
        f"Question: {question}\n\nResponses from different models:\n" +
        "\n".join(f"Model {r['model']}: {r.get('response','error')[:300]}" for r in responses) +
        "\n\nSynthesize the best answer from all responses.",
        max_tokens=800, temperature=0.2)
    return {"question": question, "responses": responses, "synthesis": synthesis or ""}

def error_correction(code_or_text: str, error_msg: str) -> Dict[str, Any]:
    """Analyze and fix errors in code or text."""
    from providers import AI
    analysis = AI.generate(
        f"Analyze this error and identify the root cause:\nCode/Text: {code_or_text[:1000]}\nError: {error_msg}\nRoot cause:",
        max_tokens=300, temperature=0.2)
    fix = AI.generate(
        f"Fix the error:\nCode/Text: {code_or_text[:1000]}\nError: {error_msg}\nAnalysis: {analysis}\nFixed version:",
        max_tokens=1500, temperature=0.2)
    return {"analysis": analysis or "", "fix": fix or ""}
