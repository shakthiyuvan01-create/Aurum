import traceback


def watchdog(function):

    try:

        function()

    except Exception:

        traceback.print_exc()