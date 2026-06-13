import importlib


def check_dependency(package):

    try:

        importlib.import_module(package)

        return True

    except:

        return False