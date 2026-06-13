from datetime import datetime


def log(text):

    with open(
        "evolution/log.txt",
        "a",
        encoding="utf8"
    ) as f:

        f.write(
            f"{datetime.now()} : {text}\n"
        )