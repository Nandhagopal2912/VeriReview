import json
from pathlib import Path

USERS_DIR = Path("users")
TEAMS_DIR = Path("teams")


def load_user(name):
    with open(USERS_DIR / f"{name}.json") as f:
        return json.load(f)


def load_team(name):
    try:
        with open(TEAMS_DIR / f"{name}.json") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
