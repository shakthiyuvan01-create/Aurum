import time
import traceback

from backup_manager import backup_project
from ceo_agent import think
from learning_agent import learn
from auto_programmer import evolve
from tester import run_tests
from github_agent import push_changes
from logger_agent import log


SLEEP_TIME = 60


def evolution_cycle():

    print("\n==========================")
    print("EVOLUTION CYCLE STARTED")
    print("==========================")

    try:

        # print("Creating backup...")
        # backup_project()

        print("CEO Agent thinking...")
        ideas = think()

        print("Ideas:")
        print(ideas)

        print("Learning...")
        response = learn()

        print(response)

        print("Running auto programmer...")
        evolve()

        print("Running tests...")
        success, error = run_tests()

        if success:
            print("Tests passed")

            try:
                push_changes()
                print("GitHub push completed")
            except Exception as e:
                print("GitHub push failed")
                print(e)

        else:
            print("Tests failed")
            print(error)

    except Exception as e:

        print("\nERROR OCCURRED")

        print(e)

        traceback.print_exc()

        log(str(e))


def main():

    print("==========================")
    print("ASSIST NEO EVOLUTION")
    print("==========================")

    while True:

        evolution_cycle()

        print()
        print("Sleeping for", SLEEP_TIME, "seconds")

        time.sleep(SLEEP_TIME)


if __name__ == "__main__":

    main()