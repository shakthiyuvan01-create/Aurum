import os


def apply_patch(patch_file):

    print()
    print("Applying patch:")
    print(patch_file)

    # For now, just open and display it

    with open(patch_file, "r", encoding="utf-8") as f:

        code = f.read()

    print(code[:500])

    return True