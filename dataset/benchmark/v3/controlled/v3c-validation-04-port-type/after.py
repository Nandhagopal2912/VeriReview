def bind_address(host, port):
    if not isinstance(port, int):
        raise TypeError("port must be an int")
    return f"{host}:{port}"
