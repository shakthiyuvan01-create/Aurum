import os


def scan():

    python_files = []

    for root, dirs, files in os.walk("."):

        if ".venv" in root:
            continue

        if "__pycache__" in root:
            continue

        for file in files:

            if file.endswith(".py"):

                python_files.append(
                    os.path.join(root, file)
                )

    return python_files


if __name__ == "__main__":

    files = scan()

    print()

    print("Python files found:")

    for file in files:

        print(file)