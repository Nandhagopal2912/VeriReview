import contextlib
import os


def clear_cache(path):
    with contextlib.suppress(FileNotFoundError):
        os.remove(path)
