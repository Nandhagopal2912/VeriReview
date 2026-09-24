from typing import Callable

distance = Callable[[tuple, tuple], float]


def length(points, d):
    return sum(d(a, b) for a, b in zip(points, points[1:]))
