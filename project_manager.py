import os


def project_stats():

    py_files = 0

    total_size = 0

    for root, dirs, files in os.walk("."):

        if ".venv" in root:
            continue

        for file in files:

            if file.endswith(".py"):

                py_files += 1

                total_size += os.path.getsize(
                    os.path.join(root, file)
                )

    return {

        "python_files": py_files,

        "size": total_size

    }