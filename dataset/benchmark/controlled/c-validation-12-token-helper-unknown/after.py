from api import auth


def fetch_profile(session, token):
    token = auth.ensure(token)
    return session.get("/me", headers={"Authorization": f"Bearer {token}"})
