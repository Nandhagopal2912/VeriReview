from jobs.resilience import resilient


@resilient
def fetch_feed(client, url):
    return client.get(url).text
