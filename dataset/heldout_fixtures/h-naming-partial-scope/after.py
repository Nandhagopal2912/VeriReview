def render(rows):
    out = []
    for index, row in enumerate(rows):
        out.append(f"{index}: {row}")
    for i in range(3):
        out.append("-")
    return out
