def send(sock, data):
    try:
        sock.sendall(data)
    except TimeoutError:
        return None
    return True
