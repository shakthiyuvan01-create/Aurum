FORBIDDEN = [

    "delete assistant.py",

    "format c:",

    "rm -rf",

    "shutdown"

]


def safe(text):

    low = text.lower()

    for x in FORBIDDEN:

        if x in low:

            return False

    return True