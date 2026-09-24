import pytest

from mathx.ratio import ratio


def test_zero_divisor_raises():
    with pytest.raises(ValueError):
        ratio(1, 0)
