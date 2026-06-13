import json

MEMORY_FILE = "evolution/memory.json"


def load_memory():

    try:

        with open(MEMORY_FILE, "r") as f:

            return json.load(f)

    except:

        return []


def remember(data):

    memory = load_memory()

    memory.append(data)

    with open(MEMORY_FILE, "w") as f:

        json.dump(memory, f, indent=4)