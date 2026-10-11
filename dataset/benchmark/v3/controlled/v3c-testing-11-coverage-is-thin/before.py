def render_row(values, width=8):
    return " | ".join(str(v).ljust(width) for v in values)
