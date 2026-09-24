import sqlite3
from contextlib import closing


def export(path):
    with closing(sqlite3.connect(path)) as conn:
        return conn.execute("SELECT * FROM t").fetchall()
