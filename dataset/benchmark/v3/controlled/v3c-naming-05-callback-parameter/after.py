def run_task(task, on_done=None):
    result = task()
    if on_done is not None:
        on_done(result)
    return result


def run_and_print(task):
    return run_task(task, on_done=print)
