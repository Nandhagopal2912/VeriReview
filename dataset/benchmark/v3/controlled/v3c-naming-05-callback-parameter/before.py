def run_task(task, cb=None):
    result = task()
    if cb is not None:
        cb(result)
    return result


def run_and_print(task):
    return run_task(task, cb=print)
