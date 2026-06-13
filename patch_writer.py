import os
from datetime import datetime


PATCH_DIR = "evolution/patches"


def save_patch(name, code):

    os.makedirs(PATCH_DIR, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    filename = os.path.join(
        PATCH_DIR,
        f"{timestamp}_{name}.py"
    )

    with open(filename, "w", encoding="utf-8") as f:

        f.write(code)

    print()

    print("Patch saved:")

    print(filename)

    return filename