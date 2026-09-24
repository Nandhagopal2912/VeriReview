from unittest import mock

import pytest
import requests

from clients.quote import quote


def test_timeout():
    with mock.patch("requests.get", side_effect=requests.Timeout):
        with pytest.raises(requests.Timeout):
            quote("https://example.com")
