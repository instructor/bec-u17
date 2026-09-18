"""
load_turnierkatalog.py
Phase 1: laedt die beiden BEC-U17-Turnierkatalog-Excel-Dateien
(_TOURNAMENT_DATA/BEC-U17-Circuit/*.xlsx) in die Tabelle "turnier" von u17_int.db.

Idempotent: UNIQUE(tournament_id) in schema.sql -- ein erneuter Lauf aktualisiert
bestehende Zeilen (UPSERT) statt sie zu duplizieren, ausser dem einmal gesetzten
scraped_at-Feld (siehe Kommentar unten).

Entscheidung (User, 2026-09-18): UseInRanking=False-Zeilen werden mit aufgenommen --
dieses Flag stammt aus der BRAIN-DBV-Pipeline und betrifft die DBV-U19-Ranglisten-
Eligibilitaet, nicht die Vollstaendigkeit des BEC-Circuits.
"""
import glob
import os
import sqlite3

import pandas as pd

DB_PATH = "u17_int.db"
CATALOG_DIR = os.path.join("_TOURNAMENT_DATA", "BEC-U17-Circuit")
URL_TEMPLATE = "https://www.tournamentsoftware.com/tournament/{code}"


def load_catalog_files():
    paths = sorted(glob.glob(os.path.join(CATALOG_DIR, "*.xlsx")))
    if not paths:
        raise FileNotFoundError(f"Keine Turnierkatalog-Excel-Dateien in {CATALOG_DIR} gefunden.")

    frames = []
    for path in paths:
        df = pd.read_excel(path)
        df["_quelle_excel"] = os.path.basename(path)
        frames.append(df)
        print(f"  gelesen: {os.path.basename(path)} ({len(df)} Zeilen)")

    return pd.concat(frames, ignore_index=True)


def upsert_turnier(conn, row):
    tournament_code = str(row["TournamentCode"]).strip()
    url = URL_TEMPLATE.format(code=tournament_code) if tournament_code else None

    conn.execute(
        """
        INSERT INTO turnier (
            ranking_tournament_id, tournament_id, tournament_code, name,
            jahr, kw, land, bec17type, grading, use_in_ranking, url, quelle_excel
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(tournament_id) DO UPDATE SET
            ranking_tournament_id = excluded.ranking_tournament_id,
            tournament_code       = excluded.tournament_code,
            name                  = excluded.name,
            jahr                  = excluded.jahr,
            kw                    = excluded.kw,
            land                  = excluded.land,
            bec17type             = excluded.bec17type,
            grading               = excluded.grading,
            use_in_ranking        = excluded.use_in_ranking,
            url                   = excluded.url,
            quelle_excel          = excluded.quelle_excel
        """,
        (
            int(row["RankingTournamentID"]),
            int(row["TournamentID"]),
            tournament_code,
            str(row["RankingTournamentName"]).strip(),
            int(row["YearNr"]),
            int(row["WeekNr"]) if pd.notna(row["WeekNr"]) else None,
            str(row["Country"]).strip() if pd.notna(row["Country"]) else None,
            str(row["BEC17type"]).strip() if pd.notna(row["BEC17type"]) else None,
            str(row["Grading"]).strip() if pd.notna(row["Grading"]) else None,
            bool(row["UseInRanking"]) if pd.notna(row["UseInRanking"]) else None,
            url,
            row["_quelle_excel"],
        ),
    )


def main():
    print("Lade Turnierkatalog ...")
    df = load_catalog_files()

    dupes = df["TournamentID"].duplicated(keep=False)
    if dupes.any():
        print("WARNUNG: doppelte TournamentID ueber beide Dateien hinweg:")
        print(df.loc[dupes, ["TournamentID", "RankingTournamentName", "_quelle_excel"]])

    conn = sqlite3.connect(DB_PATH)
    try:
        for _, row in df.iterrows():
            upsert_turnier(conn, row)
        conn.commit()
    finally:
        n_turniere = conn.execute("SELECT COUNT(*) FROM turnier").fetchone()[0]
        n_no_use = conn.execute(
            "SELECT COUNT(*) FROM turnier WHERE use_in_ranking = 0"
        ).fetchone()[0]
        conn.close()

    print(f"OK: {len(df)} Zeilen aus {df['_quelle_excel'].nunique()} Datei(en) verarbeitet.")
    print(f"    turnier-Tabelle enthaelt jetzt {n_turniere} Zeilen (davon {n_no_use} mit UseInRanking=False).")


if __name__ == "__main__":
    main()
