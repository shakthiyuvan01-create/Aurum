FORBIDDEN = [
    "rm -rf",
    "format c:",
    "shutdown",
    "os.remove",
    "shutil.rmtree"
]


def validate(code):

    low = code.lower()

    for x in FORBIDDEN:

        if x in low:

            return False

    return True