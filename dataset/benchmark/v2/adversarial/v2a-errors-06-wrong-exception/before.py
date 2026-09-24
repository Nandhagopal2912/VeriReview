def send(sock, data):
    sock.sendall(data)
    return True
