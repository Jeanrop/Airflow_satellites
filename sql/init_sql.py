import os

import psycopg
from dotenv import load_dotenv

load_dotenv()


def init_database(sql_path: str = "init.sql") -> None:
    """Apply the init script (idempotent)."""
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as conn:
        with open(sql_path, encoding="utf-8") as f:
            conn.execute(f.read())
    print("Base initialisée")


if __name__ == "__main__":
    init_database()