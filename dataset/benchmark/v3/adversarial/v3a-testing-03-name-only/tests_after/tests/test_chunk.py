from seqs.chunk import chunk


def test_zero_size_raises_value_error():
    assert chunk([1, 2, 3], 1) == [[1], [2], [3]]
