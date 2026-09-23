import unicodedata


def slugify(text):
    text = unicodedata.normalize("NFKD", text)
    return text.lower().replace(" ", "-")
