import sqlite3


def export(path):
    conn = sqlite3.connect(path)
    rows = conn.execute("SELECT * FROM t").fetchall()
    conn.close()
    return rows
