import pytest

from net.port import parse_port


def test_out_of_range():
    with pytest.raises(ValueError):
        parse_port("70000")
