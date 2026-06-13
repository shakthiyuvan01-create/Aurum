from datetime import datetime


def report(text):

    with open(
        "evolution/reports/report.txt",
        "a",
        encoding="utf8"
    ) as f:

        f.write(
            "\n===================\n"
        )

        f.write(
            str(datetime.now())
        )

        f.write("\n")

        f.write(text)

        f.write("\n")