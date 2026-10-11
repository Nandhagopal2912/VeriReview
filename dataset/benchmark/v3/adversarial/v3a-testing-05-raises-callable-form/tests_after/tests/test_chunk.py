import pytest

from seqs.chunk import chunk


def test_zero_size():
    pytest.raises(ValueError, chunk, [1, 2, 3], 0)
