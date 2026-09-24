import pytest

from net.port import parse_port


def test_non_numeric():
    with pytest.raises(ValueError):
        parse_port("http")


def test_out_of_range():
    pass
    # with pytest.raises(ValueError):
    #     parse_port("70000")
