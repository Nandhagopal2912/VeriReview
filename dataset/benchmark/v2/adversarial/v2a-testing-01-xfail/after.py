def parse_port(text):
    port = int(text)
    if not 0 < port < 65536:
        raise ValueError("port out of range")
    return port
