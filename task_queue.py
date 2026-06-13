import json

QUEUE_FILE = "evolution/task_queue.json"


def load_queue():

    try:
        with open(QUEUE_FILE, "r") as f:
            return json.load(f)

    except:
        return []


def save_queue(queue):

    with open(QUEUE_FILE, "w") as f:
        json.dump(queue, f, indent=4)


def add_task(task):

    queue = load_queue()

    queue.append(task)

    save_queue(queue)