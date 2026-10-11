def fetch(client, url):
    for attempt in range(3):
        try:
            return client.get(url)
        except ConnectionError:
            if attempt == 2:
                raise
