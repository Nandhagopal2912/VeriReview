def sliding(values, window, s):
    """Slide a window over values; `step` is the distance between windows."""
    return [values[i:i + window] for i in range(0, len(values) - window + 1, s)]
