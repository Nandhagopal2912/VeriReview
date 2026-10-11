class Mgr:
    def __init__(self):
        self.sessions = {}

    def open(self, user):
        self.sessions[user] = True


def login(manager: Mgr, user):
    manager.open(user)


default_manager = Mgr()
