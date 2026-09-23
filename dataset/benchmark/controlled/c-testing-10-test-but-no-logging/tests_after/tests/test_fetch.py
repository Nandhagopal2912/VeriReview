from unittest import mock

import requests

from clients.fetch import fetch


def test_timeout_returns_none():
    with mock.patch("requests.get", side_effect=requests.Timeout):
        assert fetch("https://example.com") is None
