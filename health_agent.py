import psutil


def health():

    return {

        "cpu": psutil.cpu_percent(),

        "ram": psutil.virtual_memory().percent
    }