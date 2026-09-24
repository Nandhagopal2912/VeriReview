def fetch_feed(client, url):
    return client.get(url).text
