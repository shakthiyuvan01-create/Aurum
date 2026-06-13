import subprocess


def execute_patch(path):

    try:

        subprocess.run(
            ["python", path],
            check=True
        )

        return True

    except Exception as e:

        print(e)

        return False