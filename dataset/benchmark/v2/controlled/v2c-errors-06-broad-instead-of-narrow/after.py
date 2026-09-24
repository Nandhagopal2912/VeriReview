def ping(sock, payload):
    try:
        sock.sendall(payload)
        return sock.recv(64)
    except Exception:
        return None
