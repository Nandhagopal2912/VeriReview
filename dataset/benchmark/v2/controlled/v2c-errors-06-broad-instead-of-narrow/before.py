def ping(sock, payload):
    sock.sendall(payload)
    return sock.recv(64)
