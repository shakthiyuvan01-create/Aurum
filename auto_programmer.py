from planner import plan
from coder import generate_code
from tester import run_tests
from memory_manager import remember


def evolve():

    tasks = plan()

    for task in tasks:

        if task["status"] == "pending":

            print()
            print("Working on:")
            print(task["idea"])

            result = generate_code(task["idea"])

            success = run_tests()

            if success:

                task["status"] = "done"

                remember(
                    {
                        "idea": task["idea"],
                        "result": "success"
                    }
                )

            else:

                remember(
                    {
                        "idea": task["idea"],
                        "result": "failed"
                    }
                )