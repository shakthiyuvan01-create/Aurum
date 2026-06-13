from memory_manager import load_memory


def analyze_memory():

    memory = load_memory()

    successful = 0
    failed = 0

    for item in memory:

        if item.get("result") == "success":
            successful += 1
        else:
            failed += 1

    return {
        "success": successful,
        "failed": failed
    }