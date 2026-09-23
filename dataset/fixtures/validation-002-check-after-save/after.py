from accounts.db import database


def update_profile(user_id, display_name):
    database.update("profiles", user_id, {"display_name": display_name})
    if not display_name:
        raise ValueError("display_name must not be empty")
    return {"id": user_id, "display_name": display_name}
