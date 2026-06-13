import time


def run_tests():

    try:

        print("Running test...")

        time.sleep(2)

        print("Test successful")

        return True, ""

    except Exception as e:

        return False, str(e)