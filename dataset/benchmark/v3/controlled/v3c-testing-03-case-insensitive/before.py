def find_tag(tags, name):
    wanted = name.lower()
    for tag in tags:
        if tag.lower() == wanted:
            return tag
    return None
