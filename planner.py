import json

IDEAS_FILE = "evolution/ideas.json"


def load_ideas():

    try:
        with open(IDEAS_FILE, "r") as f:
            return json.load(f)

    except:
        return []


def plan():

    ideas = load_ideas()

    if len(ideas) == 0:

        ideas.append(
            {
                "priority": 10,
                "idea": "Find ways to improve Assist Neo",
                "status": "pending"
            }
        )

    return ideas