import os


PATCH_DIR = "evolution/patches"


def latest_patch():

    files = [
        os.path.join(PATCH_DIR, f)
        for f in os.listdir(PATCH_DIR)
        if f.endswith(".py")
    ]

    if not files:
        return None

    files.sort()

    return files[-1]


def apply_patch():

    patch = latest_patch()

    if patch is None:

        print("No patches found")

        return False

    print()
    print("Latest patch:")
    print(patch)

    with open(patch, "r", encoding="utf-8") as f:

        code = f.read()

    print()
    print(code[:500])

    return True