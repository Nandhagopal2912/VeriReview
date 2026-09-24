import pytest

from net.port import parse_port


@pytest.mark.parametrize("text", [pytest.param("0", id="zero"), pytest.param("70000", id="too-big")])
def test_out_of_range_ports_raise(text):
    with pytest.raises(ValueError):
        parse_port(text)
