"""
tools/detective.py -- investigation instead of plain search.

Problem -> evidence -> hypotheses with confidence -> tests -> best explanation.
Built for debugging but works for any mystery.
"""
import logging

log = logging.getLogger("tools.detective")

NAME        = "detective"
DESCRIPTION = ("AI Detective: structured investigation of a problem. Gathers "
               "evidence, lists possible causes with confidence levels, and "
               "gives the best explanation plus how to verify it. "
               "Inputs: problem, evidence (logs/errors, optional).")
CATEGORY = "builtin"
ICON     = "search"
INPUTS = [
    {"name": "problem",  "label": "Problem", "type": "textarea", "required": True},
    {"name": "evidence", "label": "Evidence (logs, errors, context)", "type": "textarea"},
    {"name": "username", "label": "Username", "type": "text"},
]


def run(problem: str = "", evidence: str = "", username: str = "default") -> dict:
    if not problem.strip():
        return {"error": "problem required"}
    from providers import AI
    report = AI.generate(
        "Investigate like a detective. Structure your answer EXACTLY as:\n"
        "## Case\n(restate the problem)\n"
        "## Evidence\n(bullet everything known, note what is missing)\n"
        "## Possible causes\n(numbered, each with a confidence % and reasoning)\n"
        "## Tests to run\n(concrete commands/checks to confirm or eliminate causes)\n"
        "## Best explanation\n(most likely cause + the fix)\n\n"
        "PROBLEM: %s\n\nEVIDENCE:\n%s" % (problem, evidence or "(none provided)"),
        model="gpt-4o", max_tokens=1500, temperature=0.2)
    return {"result": report}
