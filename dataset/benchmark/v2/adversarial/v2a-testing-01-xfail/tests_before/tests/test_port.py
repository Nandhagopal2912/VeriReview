from net.port import parse_port


def test_parse_port():
    assert parse_port("8080") == 8080
