import json

STATE_FILE = "evolution/state.json"


def load_state():

    try:

        with open(STATE_FILE, "r") as f:

            return json.load(f)

    except:

        return {
            "cycle": 0,
            "successful_cycles": 0,
            "failed_cycles": 0
        }


def save_state(state):

    with open(STATE_FILE, "w") as f:

        json.dump(state, f, indent=4)