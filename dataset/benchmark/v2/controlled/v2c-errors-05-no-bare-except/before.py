import os


def remove_quietly(path):
    try:
        os.remove(path)
    except:
        pass
