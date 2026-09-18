"""
create_db.py
Legt (idempotent) u17_int.db anhand von schema.sql an.
"""
import os
import sqlite3

DB_PATH = "u17_int.db"
SCHEMA_PATH = "schema.sql"


def main():
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema = f.read()

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(schema)
        conn.commit()
    finally:
        conn.close()

    print(f"OK: {DB_PATH} angelegt/aktualisiert ({os.path.abspath(DB_PATH)})")


if __name__ == "__main__":
    main()
