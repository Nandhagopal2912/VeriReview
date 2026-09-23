def bio(profiles, user_id):
    try:
        return profiles[user_id]["bio"]
    except ValueError:
        return ""
