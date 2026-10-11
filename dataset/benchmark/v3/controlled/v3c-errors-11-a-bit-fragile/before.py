def send_all(server, messages):
    sent = 0
    for message in messages:
        server.send(message)
        sent += 1
    return sent
