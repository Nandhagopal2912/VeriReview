from unittest import mock


def test_out_of_range():
    with mock.patch("net.port.parse_port") as fake:
        fake("70000")
    fake.assert_called_once_with("70000")
