def slugify(title):
    if not title:
        return ""
    return "-".join(title.lower().split())
