import pytest

from seqs.chunk import chunk


def test_zero_size_raises():
    with pytest.raises(ValueError):
        chunk([1, 2, 3], 0)
