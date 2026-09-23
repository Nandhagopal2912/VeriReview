from unittest.mock import Mock, patch

from net.fetch import fetch_status


def test_fetch_status_timeout_case():
    with patch("net.fetch.requests.get", return_value=Mock(status_code=200)):
        assert fetch_status("https://example.com") == 200
