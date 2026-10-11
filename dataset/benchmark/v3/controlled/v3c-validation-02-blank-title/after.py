POSTS = []


def create_post(title, body):
    if not title.strip():
        raise ValueError("title is required")
    post = {"title": title, "body": body}
    POSTS.append(post)
    return post
