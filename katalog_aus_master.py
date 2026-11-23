"""
katalog_aus_master.py
Ergaenzt den U17-Turnierkatalog (Tabelle "turnier") um BEC-U17-Circuit-Turniere, die seit dem Bau der
Katalog-Excel (09/2026) dazugekommen sind (User-Vorgabe 2026-11-24, Plan Master-Data Phase 9 Schritt 5).

Umfang wie beim Excel-Katalog: Zeilen der DBV-Turnierliste U19_RankingTournaments_<Jahr> (jetzt aus der
Master-DB, juengster Snapshot) mit Grading "BEC U17 Circuit", fuer die Jahre, die der Katalog schon enthaelt.
Kategorie (BEC17type) aus dem BEC-Text der Turnier-Metadaten (extraData.descriptionHtml, von der Master-DB unter
ALL_INTERNATIONAL_TOURNAMENTS/.../raw/meta.json gespeichert): "U17 International Series" -> U17 IS,
"... Challenge" -> U17 IC, "... Grand Prix" -> U17 GP. Ohne erkennbaren Text wird das Turnier gemeldet und NICHT
aufgenommen (keine geratene Kategorie). Vorhandene Katalogzeilen werden nie geaendert.

Nur U17 (BEC_AK=U17). Aufruf:  python katalog_aus_master.py [--dry-run]
Danach load_from_master.py.
"""
import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "_BRAIN_LIB"))
import masterdata_reader as mdr  # noqa: E402

from ak_config import AK, DB_PATH  # noqa: E402

URL_TEMPLATE = "https://www.tournamentsoftware.com/tournament/{code}"
GRADING = "BEC U17 Circuit"
KATEGORIE = [(re.compile(r"U17\s+International\s+Series", re.I), "U17 IS"),
             (re.compile(r"U17\s+International\s+Challenge", re.I), "U17 IC"),
             (re.compile(r"U17\s+Grand\s+Prix", re.I), "U17 GP")]


def kategorie_aus_meta(m, code):
    r = m.execute("SELECT verzeichnis FROM international_tournament WHERE upper(code) = upper(?)", (code,)).fetchone()
    if not r or not r["verzeichnis"]:
        return None, "nicht in der Master-DB"
    meta = mdr.base_dir() / r["verzeichnis"] / "raw" / "meta.json"
    if not meta.exists():
        return None, "keine meta.json"
    html = (json.loads(meta.read_text("utf-8")).get("extraData") or {}).get("descriptionHtml") or ""
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()
    for rx, kat in KATEGORIE:
        if rx.search(text):
            return kat, text[:60]
    return None, f"Text ohne Kategorie: {text[:60]!r}"


def main():
    if AK != "U17":
        sys.exit("nur fuer BEC_AK=U17 (U19-Kategorien stehen nicht im BEC-Text)")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    conn = sqlite3.connect(DB_PATH)
    vorhanden = {c.upper() for (c,) in conn.execute("SELECT tournament_code FROM turnier") if c}
    jahre = [j for (j,) in conn.execute("SELECT DISTINCT jahr FROM turnier ORDER BY 1")]
    # Nur Turniere NACH dem juengsten Katalogturnier: aeltere, die in der Liste stehen, aber im Excel-Katalog
    # fehlen (Adria U17 2025, Liepaja Beach U17 2025 -- schon im 03/2026 als BEC U17 Circuit gefuehrt), hat der
    # User bewusst weggelassen; sie werden nur gemeldet.
    grenze = conn.execute("SELECT MAX(jahr * 100 + kw) FROM turnier WHERE quelle_excel NOT LIKE 'master:%'").fetchone()[0]
    neu, ohne, frueher = [], [], []
    with mdr.connect() as m:
        for jahr in jahre:
            pfad = mdr.liste("tournaments", jahr)
            df = pd.read_excel(pfad) if str(pfad).endswith(".xlsx") else pd.read_csv(pfad, sep=None, engine="python")
            df = df[df["Grading"].astype(str).str.strip() == GRADING]
            for _, r in df.iterrows():
                code = str(r["TournamentCode"]).strip().upper()
                if code in vorhanden:
                    continue
                if int(r["YearNr"]) * 100 + int(r["WeekNr"]) <= grenze:
                    frueher.append(r)
                    continue
                kat, info = kategorie_aus_meta(m, code)
                eintrag = (r, code, kat, info, Path(pfad).name)
                (neu if kat else ohne).append(eintrag)
    for r, code, kat, info, quelle in neu:
        print(f"  NEU  {int(r['YearNr'])} KW{int(r['WeekNr']):02d}  {kat}  {r['RankingTournamentName']}  ({info})")
        if not a.dry_run:
            conn.execute(
                "INSERT INTO turnier (ranking_tournament_id, tournament_id, tournament_code, name, jahr, kw, land, "
                "bec17type, grading, use_in_ranking, url, quelle_excel) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (int(r["RankingTournamentID"]), int(r["TournamentID"]), code, str(r["RankingTournamentName"]).strip(),
                 int(r["YearNr"]), int(r["WeekNr"]), str(r["Country"]).strip(), kat, GRADING,
                 str(r["UseInRanking"]).strip().lower() in ("true", "1", "wahr"), URL_TEMPLATE.format(code=code),
                 f"master:{quelle}"))
    for r, code, kat, info, quelle in ohne:
        print(f"  OHNE KATEGORIE (nicht aufgenommen)  {int(r['YearNr'])} KW{int(r['WeekNr']):02d}  "
              f"{r['RankingTournamentName']}: {info}")
    for r in frueher:
        print(f"  NICHT IM KATALOG, aelter als {grenze // 100} KW{grenze % 100:02d} (bewusst ausgelassen?)  "
              f"{int(r['YearNr'])} KW{int(r['WeekNr']):02d}  {r['RankingTournamentName']}")
    print(f"{len(neu)} neu aufgenommen, {len(ohne)} ohne Kategorie" + (" (dry-run, nichts gespeichert)" if a.dry_run else ""))
    if not a.dry_run:
        conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
