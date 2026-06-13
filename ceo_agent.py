from ai_brain import ask_ai


def think():
    prompt = """
    You are the CEO of Assist Neo.

    Assist Neo is a Python AI assistant.

    Suggest only small coding improvements that can be implemented immediately.

    Examples:

    Add voice mode.
    Improve memory.
    Improve GUI.
    Improve image analysis.
    Improve plugin system.
    Improve logging.
    Improve error handling.
    Improve speed.
    Improve code organization.

    Rules:

    - Return at most 5 ideas.
    - One line per idea.
    - No business ideas.
    - No employee training.
    - No customer support.
    - No cloud infrastructure.
    - No unrealistic features.
    """

    response = ask_ai(prompt)

    if not response:
        return []

    ideas = []

    for line in response.split("\n"):

        line = line.strip()

        if len(line) > 5:

            ideas.append(line)

    return ideas