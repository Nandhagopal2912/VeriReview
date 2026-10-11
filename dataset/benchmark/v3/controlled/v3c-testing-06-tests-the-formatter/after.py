def parse_duration(text):
    seconds = int(text.rstrip("s"))
    if seconds < 0:
        raise ValueError("duration must not be negative")
    return seconds


def format_duration(seconds):
    return f"{seconds}s"
