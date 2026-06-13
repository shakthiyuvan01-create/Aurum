import shutil


def rollback(backup_folder):

    try:

        shutil.copytree(
            backup_folder,
            ".",
            dirs_exist_ok=True
        )

        return True

    except Exception as e:

        print(e)

        return False