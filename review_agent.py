import os


def inspect():

    problems = []

    for root, dirs, files in os.walk("."):

        if ".venv" in root:
            continue

        for file in files:

            if file.endswith(".py"):

                path = os.path.join(root, file)

                size = os.path.getsize(path)

                if size > 100000:

                    problems.append(
                        f"{file} is too large."
                    )

    return problems