"""
compute_rangliste.py
Phase 3: berechnet die Punkte-Rangliste je Disziplin (Best-of-N ueber alle Turnierergebnisse
eines Spielers) aus turnier_ergebnisse + punktetabelle und schreibt sie nach "rangliste".

Bei Doppel/Mixed (spieler2_id gesetzt) bekommen BEIDE Partner die vollen Punkte fuer diese
Platzierung individuell angerechnet -- jeder Spieler hat eine eigene Rangliste je Disziplin,
unabhaengig vom jeweiligen Partner (Standard-Konvention, analog bec_u15_auswertung).

BEST_OF_N=3 ist ein Startwert (analog bec_u15_auswertung, noch nicht mit dem User final
abgestimmt) -- leicht anzupassen, siehe CLAUDE.md.
"""
import os
import sqlite3
from collections import defaultdict

import pandas as pd

DB_PATH = "u17_int.db"
OUT_DIR = "_RESULTS"
BEST_OF_N = 3


def main():
    conn = sqlite3.connect(DB_PATH)
    try:
        points_lookup = dict(
            conn.execute("SELECT platz, punkte FROM punktetabelle WHERE bec17type IS NULL").fetchall()
        )

        rows = conn.execute(
            "SELECT disziplin, platzierung, spieler1_id, spieler2_id FROM turnier_ergebnisse"
        ).fetchall()

        player_results = defaultdict(list)  # (spieler_id, disziplin) -> [punkte, ...]
        missing_platz = set()
        for disziplin, platzierung, s1, s2 in rows:
            punkte = points_lookup.get(platzierung)
            if punkte is None:
                missing_platz.add(platzierung)
                continue
            for sid in (s1, s2):
                if sid is not None:
                    player_results[(sid, disziplin)].append(punkte)

        if missing_platz:
            print(f"WARNUNG: keine Punktetabellen-Zeile fuer Platzierungen {sorted(missing_platz)} "
                  f"-- diese Ergebnisse wurden nicht gewertet.")

        conn.execute("DELETE FROM rangliste")
        for (sid, disziplin), punkte_liste in player_results.items():
            top_n = sorted(punkte_liste, reverse=True)[:BEST_OF_N]
            conn.execute(
                "INSERT INTO rangliste (spieler_id, disziplin, punkte, anzahl_turniere) VALUES (?, ?, ?, ?)",
                (sid, disziplin, sum(top_n), len(punkte_liste)),
            )
        conn.commit()

        n_spieler_disziplin = len(player_results)
        print(f"OK: {n_spieler_disziplin} (Spieler, Disziplin)-Kombinationen in rangliste geschrieben "
              f"(Best-of-{BEST_OF_N}).")

        export_csv(conn)
    finally:
        conn.close()


def export_csv(conn):
    os.makedirs(OUT_DIR, exist_ok=True)
    df = pd.read_sql_query(
        """
        SELECT r.disziplin, r.punkte, r.anzahl_turniere,
               p.vorname, p.name, p.nation, p.bec_player_id
        FROM rangliste r
        JOIN player p ON p.spieler_id = r.spieler_id
        """,
        conn,
    )
    for disziplin, group in df.groupby("disziplin"):
        group = group.sort_values("punkte", ascending=False).reset_index(drop=True)
        group.insert(0, "rang", group.index + 1)
        path = os.path.join(OUT_DIR, f"rangliste_{disziplin}.csv")
        group.to_csv(path, index=False, encoding="utf-8-sig", sep=";")
        print(f"  -> {path} ({len(group)} Spieler)")


if __name__ == "__main__":
    main()
