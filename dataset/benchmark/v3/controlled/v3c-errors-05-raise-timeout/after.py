import time


def wait_until(check, deadline):
    while time.monotonic() < deadline:
        if check():
            return True
        time.sleep(0.1)
    raise TimeoutError("condition not met before the deadline")
