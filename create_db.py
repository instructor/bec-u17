"""
create_db.py
Legt (idempotent) u17_int.db anhand von schema.sql an. Neue Tabellen kommen ueber
"CREATE TABLE IF NOT EXISTS" automatisch dazu; neue SPALTEN an bestehenden Tabellen (z.B.
turnier.entries_scraped_at) muessen hier per ALTER TABLE nachgezogen werden, ohne bestehende
Daten (Matches/Spieler) zu verlieren.
"""
import os
import sqlite3

DB_PATH = "u17_int.db"
SCHEMA_PATH = "schema.sql"

# (Tabelle, Spalte, SQL-Typ) -- wird nur ergaenzt, falls die Spalte noch fehlt.
EXTRA_COLUMNS = [
    ("turnier", "entries_scraped_at", "TEXT"),
    ("matches", "spieldatum", "TEXT"),
]


def ensure_columns(conn):
    for table, column, coltype in EXTRA_COLUMNS:
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
            print(f"  + Spalte {table}.{column} ergaenzt")


def main():
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema = f.read()

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(schema)
        ensure_columns(conn)
        conn.commit()
    finally:
        conn.close()

    print(f"OK: {DB_PATH} angelegt/aktualisiert ({os.path.abspath(DB_PATH)})")


if __name__ == "__main__":
    main()
