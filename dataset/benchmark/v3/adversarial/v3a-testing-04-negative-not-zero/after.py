def chunk(seq, size):
    if size <= 0:
        raise ValueError("size must be positive")
    return [seq[i : i + size] for i in range(0, len(seq), size)]
