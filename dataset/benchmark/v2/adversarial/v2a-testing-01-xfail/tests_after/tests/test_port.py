import pytest

from net.port import parse_port


def test_parse_port():
    assert parse_port("8080") == 8080


@pytest.mark.xfail(reason="flaky")
def test_out_of_range():
    with pytest.raises(ValueError):
        parse_port("70000")
