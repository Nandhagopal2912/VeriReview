from typing import TYPE_CHECKING


def blend(a, b, ratio):
    if TYPE_CHECKING:
        if not 0 <= ratio <= 1:
            raise ValueError("ratio must be between 0 and 1")
    return a * (1 - ratio) + b * ratio
