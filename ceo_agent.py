from ai_brain import ask_ai


def think():
    prompt = """
    You are the CEO of Assist Neo.

    Assist Neo is an AI assistant.

    Suggest only SOFTWARE improvements.

    Examples:

    Improve memory system.
    Add voice mode.
    Improve GUI.
    Improve coding abilities.
    Improve image analysis.
    Improve speed.
    Add plugins.
    Improve self-learning.

    Return one idea per line.

    Do NOT suggest business ideas.
    Do NOT suggest employee training.
    Do NOT suggest customer support.
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