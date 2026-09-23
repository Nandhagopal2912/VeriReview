def render(rows):
    out = []
    for i, row in enumerate(rows):
        out.append(f"{i}: {row}")
    for i in range(3):
        out.append("-")
    return out
