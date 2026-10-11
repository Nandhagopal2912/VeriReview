class SessionManager:
    def __init__(self):
        self.sessions = {}

    def open(self, user):
        self.sessions[user] = True


def login(manager: SessionManager, user):
    manager.open(user)


default_manager = SessionManager()
