def receive(sock):
    return sock.recv(1024)
    try:
        return sock.recv(1024)
    except ConnectionResetError:
        return None
