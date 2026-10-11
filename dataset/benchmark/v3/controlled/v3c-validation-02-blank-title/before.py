POSTS = []


def create_post(title, body):
    post = {"title": title, "body": body}
    POSTS.append(post)
    return post
