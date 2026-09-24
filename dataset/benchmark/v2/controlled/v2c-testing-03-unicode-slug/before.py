import unicodedata


def slug(title):
    ascii_ = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    return "-".join(ascii_.lower().split())
