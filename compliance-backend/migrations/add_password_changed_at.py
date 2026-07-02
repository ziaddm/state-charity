"""
Adds users.password_changed_at (used to invalidate JWTs issued before a
password change). Safe to run multiple times.

Run from compliance-backend/:  python -m migrations.add_password_changed_at
"""
from sqlalchemy import text

from app.database.connection import engine


def run():
    with engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS password_changed_at TIMESTAMP"
        ))
    print("OK: users.password_changed_at ensured")


if __name__ == "__main__":
    run()
