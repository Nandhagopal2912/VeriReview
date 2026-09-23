def listen(host, port):
    if not isinstance(port, int):
        raise TypeError("port must be an int")
    return (host, port)
