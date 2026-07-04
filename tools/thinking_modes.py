"""
tools/thinking_modes.py -- five structured reasoning modes in one tool.

  innovate   -- invention engine: ideas + feasibility + patent potential + market
  strategize -- strategy mode: resources, constraints, risks, best/expected/
                worst scenarios, critical path, failure probability, recovery
  resolve    -- conflict resolver: compare disagreeing sources, find the
                contradiction, explain which is right and why
  textbook   -- turn a topic (plus what the user already knows) into a
                mini-textbook: chapters, examples, quiz, revision notes
  questions  -- generate the smarter questions people forget to ask
"""
import logging

log = logging.getLogger("tools.thinking_modes")

NAME        = "thinking_modes"
DESCRIPTION = ("Structured reasoning modes: innovate (invention ideas + "
               "feasibility), strategize (scenarios + risks + critical path + "
               "failure %), resolve (conflicting sources), textbook (learn a "
               "topic as a book), questions (smarter follow-up questions). "
               "Inputs: mode, topic, context (optional).")
CATEGORY = "builtin"
ICON     = "bulb"
INPUTS = [
    {"name": "mode", "label": "Mode", "type": "select",
     "options": [{"value": m, "label": m} for m in
                 ("innovate", "strategize", "resolve", "textbook", "questions", "negotiate")],
     "required": True},
    {"name": "topic",   "label": "Topic / goal / question", "type": "textarea", "required": True},
    {"name": "context", "label": "Extra context (sources, constraints...)", "type": "textarea"},
    {"name": "username", "label": "Username", "type": "text"},
]

_PROMPTS = {
    "innovate": (
        "You are an invention engine. For the goal below, produce 3 genuinely "
        "novel ideas. For EACH: ## Idea N: name -- how it works (specific "
        "mechanism), why it is new vs existing solutions, feasibility score /10 "
        "with the hardest engineering problem, patent potential (what claim "
        "might be novel), and rough market value. End with which idea to "
        "prototype first and the first experiment to run."),
    "strategize": (
        "You are a strategist. For the goal below produce: ## Resources needed "
        "| ## Constraints | ## Competition/landscape | ## Risks (each with "
        "probability and mitigation) | ## Scenarios: Best case, Expected, Worst "
        "case (each with concrete outcomes) | ## Recovery plan if worst case "
        "hits | ## Critical path (ordered tasks, note which can run in "
        "parallel) | ## Failure probability: X% because... | ## Timeline."),
    "resolve": (
        "Two or more sources disagree. Lay out: ## What each source claims "
        "(with its likely reliability %) | ## The exact contradiction | "
        "## Possible explanations (different definitions? outdated data? "
        "different contexts?) | ## Which is most likely correct and why | "
        "## How to verify definitively."),
    "textbook": (
        "Write a mini-textbook on the topic: ## Chapter list (5-7) | then for "
        "the 2 most important chapters write the full content with worked "
        "examples | ## Quiz (5 questions with answers hidden at the end) | "
        "## One-page revision summary. Adapt depth to the stated context."),
    "negotiate": (
        "You are a contract negotiator. For the contract/deal text or "
        "description below: ## Key terms summary | ## Risks and unfavorable "
        "clauses (each with severity and why) | ## Missing protections | "
        "## Suggested changes (exact replacement wording) | ## Negotiation "
        "strategy (what to concede, what to hold) | ## Draft counter-message."),
    "questions": (
        "Generate the 10 smarter questions about this topic that people "
        "usually forget to ask -- the ones an expert would ask. Group them: "
        "assumptions worth challenging, second-order effects, edge cases, "
        "and what-nobody-measures. One line each, no answers."),
}


def run(mode: str = "questions", topic: str = "", context: str = "",
        username: str = "default") -> dict:
    mode = (mode or "questions").lower().strip()
    if mode not in _PROMPTS:
        return {"error": "mode must be one of: " + ", ".join(_PROMPTS)}
    if not topic.strip():
        return {"error": "topic required"}
    from providers import AI
    out = AI.generate(
        _PROMPTS[mode] + "\n\nTOPIC/GOAL: " + topic +
        ("\n\nCONTEXT:\n" + context if context.strip() else ""),
        model="gpt-4o", max_tokens=2200, temperature=0.4)
    return {"result": out, "mode": mode}
