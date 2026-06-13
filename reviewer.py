import os


def review():

    ideas = []

    for root, dirs, files in os.walk("."):

        if ".venv" in root:
            continue

        for file in files:

            if file.endswith(".py"):

                path = os.path.join(root, file)

                size = os.path.getsize(path)

                # detect large files
                if size > 100000:

                    ideas.append(
                        f"{file} is too large. Split into modules."
                    )

    return ideas