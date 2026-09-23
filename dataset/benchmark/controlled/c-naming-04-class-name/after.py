class UserManager:
    def __init__(self, db):
        self.db = db

    def get(self, user_id):
        return self.db.find(user_id)


def default_manager(db):
    return UserManager(db)
