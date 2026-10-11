from net.fetch import fetch


class FlakyClient:
    def __init__(self):
        self.calls = 0

    def get(self, url):
        self.calls += 1
        if self.calls == 1:
            raise ConnectionError
        return "ok"


def test_retries_after_a_connection_error():
    client = FlakyClient()
    assert fetch(client, "http://example.org") == "ok"
    assert client.calls == 2
