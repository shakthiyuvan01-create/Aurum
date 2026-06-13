import time


start = time.time()


def metrics():

    uptime = time.time() - start

    return {

        "uptime": uptime

    }