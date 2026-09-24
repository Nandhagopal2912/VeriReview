from contextlib import ExitStack


def merge(paths, out):
    with ExitStack() as stack:
        handles = [stack.enter_context(open(p)) for p in paths]
        for h in handles:
            out.write(h.read())
