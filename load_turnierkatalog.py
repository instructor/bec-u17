"""
load_turnierkatalog.py
Phase 1: laedt die Turnierkatalog-Excel-Dateien (U17: _TOURNAMENT_DATA/BEC-U17-Circuit/*.xlsx,
U19: _TOURNAMENT_DATA/BEC-U19-Junior/*.xlsx, siehe ak_config.py) in die Tabelle "turnier".
Die Typ-Spalte (BEC17type bzw. BEC19type) landet in turnier.bec17type.

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

from ak_config import DB_PATH  # u17_int.db bzw. u19_int.db, siehe ak_config.py
from ak_config import CATALOG_DIR, TYPE_COLUMN
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


def _int_or_none(v):
    return int(v) if pd.notna(v) else None


def upsert_turnier(conn, row):
    tournament_code = str(row["TournamentCode"]).strip()
    url = URL_TEMPLATE.format(code=tournament_code) if tournament_code else None
    typ = str(row[TYPE_COLUMN]).strip() if pd.notna(row[TYPE_COLUMN]) else None

    if pd.isna(row["TournamentID"]):
        # U19-Ergaenzungsliste (BEC-Kalender, nicht in der DBV-Liste): keine TournamentID, der
        # UNIQUE(tournament_id)-UPSERT greift bei NULL nicht -- deshalb ueber tournament_code
        # abgleichen, damit ein erneuter Lauf keine Duplikate erzeugt.
        values = (str(row["RankingTournamentName"]).strip(), int(row["YearNr"]), _int_or_none(row["WeekNr"]),
                  str(row["Country"]).strip() if pd.notna(row["Country"]) else None, typ, url, row["_quelle_excel"])
        existing = conn.execute("SELECT turnier_id FROM turnier WHERE tournament_code = ?", (tournament_code,)).fetchone()
        if existing:
            conn.execute("UPDATE turnier SET name=?, jahr=?, kw=?, land=?, bec17type=?, url=?, quelle_excel=? "
                         "WHERE turnier_id=?", values + (existing[0],))
        else:
            conn.execute("INSERT INTO turnier (name, jahr, kw, land, bec17type, url, quelle_excel, tournament_code) "
                         "VALUES (?, ?, ?, ?, ?, ?, ?, ?)", values + (tournament_code,))
        return

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
            _int_or_none(row["RankingTournamentID"]),
            int(row["TournamentID"]),
            tournament_code,
            str(row["RankingTournamentName"]).strip(),
            int(row["YearNr"]),
            int(row["WeekNr"]) if pd.notna(row["WeekNr"]) else None,
            str(row["Country"]).strip() if pd.notna(row["Country"]) else None,
            typ,
            str(row["Grading"]).strip() if pd.notna(row["Grading"]) else None,
            bool(row["UseInRanking"]) if pd.notna(row["UseInRanking"]) else None,
            url,
            row["_quelle_excel"],
        ),
    )


def main():
    print("Lade Turnierkatalog ...")
    df = load_catalog_files()

    dupes = df["TournamentID"].notna() & df["TournamentID"].duplicated(keep=False)
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
