def send_all(server, messages):
    sent = 0
    for message in messages:
        try:
            server.send(message)
        except OSError:
            continue
        sent += 1
    return sent
