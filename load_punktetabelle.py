"""
load_punktetabelle.py
Phase 3: befuellt "punktetabelle" mit einem einfachen, eigenstaendigen platzbasierten Schema
(User-Entscheidung 2026-09-18: KEINE Uebernahme der U15-Punktwerte -- sauberer Neustart).

Geometrische Kurve: Punkte(Platzierungs-Tiegroup i) = round(BASE_POINTS * DECAY**i), i=0,1,2,...
fuer die Tiegroup-Startplaetze, die unsere eigene Platzierungs-Herleitung
(fetch_bec_entries_winners.import_placements) tatsaechlich erzeugt: 1 (Champion), 2 (Finalist),
3 (Halbfinale), 5 (Viertelfinale), 9 (R16), 17 (R32), 33 (R64), 65 (R128), ... jeweils
2**(k-1)+1 fuer Runde k=1,2,3,...

bec17type bleibt NULL (flache, tier-unabhaengige Tabelle -- siehe CLAUDE.md, "Punktetabelle"-
Entscheidung). Idempotent (INSERT OR REPLACE ueber UNIQUE(bec17type, platz)).
"""
import sqlite3

DB_PATH = "u17_int.db"
BASE_POINTS = 1000
DECAY = 0.8
MAX_ROUNDS = 10  # deckt Platzierungen bis 2**(MAX_ROUNDS-1)+1 = 513 ab, mehr als je im BEC-U17-Circuit vorkommt


def placement_tiegroups():
    yield 1  # Champion
    for k in range(1, MAX_ROUNDS):
        yield 2 ** (k - 1) + 1  # 2, 3, 5, 9, 17, 33, 65, 129, 257, ...


def main():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM punktetabelle WHERE bec17type IS NULL")
        rows = []
        for i, platz in enumerate(placement_tiegroups()):
            punkte = round(BASE_POINTS * DECAY ** i)
            rows.append((platz, punkte))

        conn.executemany(
            "INSERT INTO punktetabelle (bec17type, platz, punkte) VALUES (NULL, ?, ?)", rows
        )
        conn.commit()

        print(f"OK: {len(rows)} Zeilen in punktetabelle (bec17type=NULL) geschrieben.")
        for platz, punkte in rows:
            print(f"  Platz {platz:4d}: {punkte:5d} Punkte")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
