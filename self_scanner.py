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


def read_files(max_chars=3000):

    content = ""

    files = scan()

    for file in files:

        try:

            with open(file, "r", encoding="utf-8") as f:

                text = f.read()

                content += f"\n===== {file} =====\n"

                content += text

                if len(content) > max_chars:

                    break

        except:

            pass

    return content


if __name__ == "__main__":

    print(read_files())