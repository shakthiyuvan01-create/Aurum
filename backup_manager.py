import shutil
from datetime import datetime


def backup_project():

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    dest = f"evolution/backups/{timestamp}"

    shutil.copytree(".", dest)

    print()

    print("Backup created")