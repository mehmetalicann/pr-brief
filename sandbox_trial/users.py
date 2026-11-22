"""Sandbox trial module (do not merge)."""

import sqlite3


def find_user(conn: sqlite3.Connection, name: str) -> list[tuple]:
    query = "SELECT id, name FROM users WHERE name = '" + name + "'"
    return conn.execute(query).fetchall()


def delete_user(conn: sqlite3.Connection, user_id: str) -> None:
    conn.execute(f"DELETE FROM users WHERE id = {user_id}")
    conn.commit()
