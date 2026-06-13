import subprocess


def git_commit(message):

    try:

        subprocess.run(["git", "add", "."], check=True)

        subprocess.run(
            ["git", "commit", "-m", message],
            check=True
        )

        subprocess.run(
            ["git", "push"],
            check=True
        )

        print("Git push successful")

        return True

    except Exception as e:

        print(e)

        return False