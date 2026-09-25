"""
build_junior_turnierliste.py
Erzeugt analog zu _TOURNAMENT_DATA/BEC-U17-Circuit/U19_RankingTournaments_<Jahr>_ausschliesslich-
BEC-U17-Differenzierung.xlsx eine Liste der Junior-(U19)-Turniere aus den DBV-Turnierlisten
(BRAIN: ALL_TOURNAMENTS+RESULT-RANKINGS/U19_RankingTournaments_<Jahr>.xlsx), ergaenzt um die
Spalte "BEC19type" (U19 WJC/EJC/JIGP/JIC/JIS/JFS).

Aufgenommen wird eine Zeile, wenn
  - ihr DBV-Grading eine Junior-Kategorie ist (JUNIOR_GRADING_TO_TYPE), oder
  - ihr TournamentCode im BEC-Kalender als Junior-Turnier gefuehrt ist (erfasst z.B. Turniere,
    die in der DBV-Liste noch als "Automatic (Based on Event Grading)" stehen).
Turniertyp: bevorzugt die BEC-Kategorie (tournamentCategory.name aus der BEC-Datenhub-API,
gecacht in _RESULTS/_debug_bec_calendar_all.json), sonst das DBV-Grading. Abweichungen zwischen
beiden werden ausgegeben.

Zusaetzlich: U19_BEC-Junior_ergaenzend_nicht-in-DBV-Liste.xlsx mit den Junior-Turnieren aus dem
BEC-Kalender ohne deutsche Beteiligung (fuer die Turnierstaerke-Auswertung).

Aufruf: python build_junior_turnierliste.py
Ergebnis: _TOURNAMENT_DATA/BEC-U19-Junior/U19_RankingTournaments_<Jahr>_ausschliesslich-BEC-U19-Junior-Differenzierung.xlsx
          _TOURNAMENT_DATA/BEC-U19-Junior/U19_BEC-Junior_ergaenzend_nicht-in-DBV-Liste.xlsx
"""
import json
import os
import sys

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 20)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(os.path.dirname(BASE_DIR), "_BRAIN_Badminton-RAnking-INsights",
                       "ALL_TOURNAMENTS+RESULT-RANKINGS")
CALENDAR = os.path.join(BASE_DIR, "_RESULTS", "_debug_bec_calendar_all.json")
OUT_DIR = os.path.join(BASE_DIR, "_TOURNAMENT_DATA", "BEC-U19-Junior")
YEARS = (2025, 2026)

JUNIOR_GRADING_TO_TYPE = {
    "JWM / Olympische Jugendspiele": "U19 WJC",
    "Jugend-EM": "U19 EJC",
    "Junior International Grand Prix": "U19 JIGP",
    "Junior International Challenge": "U19 JIC",
    "Junior International Series": "U19 JIS",
    "Junior Future Series": "U19 JFS",
}
BEC_CATEGORY_TO_TYPE = {
    "Continental Junior Individual Championships": "U19 EJC",
    "Junior International Grand Prix": "U19 JIGP",
    "Junior International Challenge": "U19 JIC",
    "Junior International Series": "U19 JIS",
}
COLUMNS = ["TournamentNumber", "RankingTournamentName", "YearNr", "WeekNr", "BEC19type", "Grading",
           "Country", "Processed", "RankingTournamentID", "TournamentID", "TournamentCode", "UseInRanking"]


def bec_types():
    """TournamentCode (Grossbuchstaben) -> BEC19type laut BEC-Kalender."""
    types = {}
    for _level, category, name, _start, code in json.load(open(CALENDAR, encoding="utf-8")):
        t = BEC_CATEGORY_TO_TYPE.get(category)
        if t is None and name and "World Junior Championships" in name and "Team" not in name:
            t = "U19 WJC"
        if t:
            types[code.upper()] = t
    return types


def build_ergaenzung(dbv_lists, bec):
    """Junior-Turniere aus dem BEC-Kalender, die in keiner DBV-Liste stehen (keine deutsche
    Beteiligung) -- fuer die Turnierstaerke-Auswertung. Gleiche Spalten wie die DBV-Listen,
    DBV-eigene Felder bleiben leer. Nur bereits begonnene, nicht abgesagte Turniere. Der
    BEC-Kalender fuehrt manche Turniere doppelt (mehrere Codes); ein Eintrag gilt deshalb auch
    dann als vorhanden, wenn ein DBV-Eintrag gleichen Typs im selben Land in derselben Jahr/KW
    existiert (bei unbekanntem Land genuegen Typ + Jahr/KW)."""
    from datetime import date
    from bec_api import get_json, NoDataAvailable

    dbv = pd.concat(dbv_lists)
    dbv_codes = set(dbv.TournamentCode.astype(str).str.upper())
    dbv_slots = set(zip(dbv.YearNr, dbv.WeekNr, dbv.BEC19type, dbv.Country))
    dbv_slots_ohne_land = {s[:3] for s in dbv_slots}
    today = date.today().isoformat()

    rows, seen = [], set()
    for _level, _cat, name, start, code in json.load(open(CALENDAR, encoding="utf-8")):
        cu = code.upper()
        typ = bec.get(cu)
        if typ is None or cu in dbv_codes or cu in seen or start[:10] > today or "Cancelled" in (name or ""):
            continue
        y, kw, _ = date.fromisoformat(start[:10]).isocalendar()
        if (y, kw, typ) not in dbv_slots_ohne_land:
            meta = {}
        else:
            try:
                meta = get_json(f"tournament/{code}")
            except NoDataAvailable:
                meta = {}
            land = meta.get("venueCountryCode")
            if land is None or (y, kw, typ, land) in dbv_slots:
                continue
        seen.add(cu)
        if not meta:
            try:
                meta = get_json(f"tournament/{code}")
            except NoDataAvailable:
                meta = {}
        rows.append({"TournamentNumber": None, "RankingTournamentName": name, "YearNr": y, "WeekNr": kw,
                     "BEC19type": typ, "Grading": None, "Country": meta.get("venueCountryCode"),
                     "Processed": None, "RankingTournamentID": None, "TournamentID": None,
                     "TournamentCode": code, "UseInRanking": None,
                     "Quelle": "BEC-Kalender, nicht in DBV-Liste"})
    out = pd.DataFrame(rows, columns=COLUMNS + ["Quelle"]).sort_values(["YearNr", "WeekNr"], ascending=False)
    # Doppelte Kalendereintraege (gleicher Name, mehrere Codes) nur einmal behalten
    out = out.drop_duplicates(subset=["RankingTournamentName", "YearNr", "WeekNr"])
    path = os.path.join(OUT_DIR, "U19_BEC-Junior_ergaenzend_nicht-in-DBV-Liste.xlsx")
    out.to_excel(path, sheet_name="Tournaments", index=False)
    print(f"\n=== Ergaenzung: {len(out)} Turniere -> {os.path.relpath(path, BASE_DIR)}")
    print(out[["YearNr", "WeekNr", "BEC19type", "Country", "RankingTournamentName"]].to_string(index=False))


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    bec = bec_types()
    dbv_lists = []
    for year in YEARS:
        src = pd.read_excel(os.path.join(SRC_DIR, f"U19_RankingTournaments_{year}.xlsx"))
        code = src.TournamentCode.astype(str).str.upper()
        typ_dbv = src.Grading.map(JUNIOR_GRADING_TO_TYPE)
        typ_bec = code.map(bec)
        keep = typ_dbv.notna() | typ_bec.notna()

        out = src[keep].copy()
        out["BEC19type"] = typ_bec[keep].fillna(typ_dbv[keep])
        out = out[COLUMNS]

        diff = keep & typ_dbv.notna() & typ_bec.notna() & (typ_dbv != typ_bec)
        path = os.path.join(OUT_DIR, f"U19_RankingTournaments_{year}_ausschliesslich-BEC-U19-Junior-Differenzierung.xlsx")
        out.to_excel(path, sheet_name="Tournaments", index=False)
        dbv_lists.append(out)

        print(f"\n=== {year}: {len(out)} Turniere -> {os.path.relpath(path, BASE_DIR)}")
        print(out.BEC19type.value_counts().to_string())
        print(f"UseInRanking=False: {(~out.UseInRanking.astype(bool)).sum()}")
        only_bec = keep & typ_dbv.isna()
        if only_bec.any():
            print("Nur ueber BEC-Kalender erkannt (DBV-Grading nicht Junior):")
            print(src[only_bec][["RankingTournamentName", "WeekNr", "Grading"]].assign(BEC19type=typ_bec[only_bec]).to_string(index=False))
        if diff.any():
            print("ABWEICHUNG DBV-Grading vs. BEC-Kategorie (BEC gewinnt):")
            print(src[diff][["RankingTournamentName", "WeekNr", "Grading"]].assign(BEC=typ_bec[diff]).to_string(index=False))
        no_bec = keep & typ_bec.isna()
        if no_bec.any():
            print("Nicht im BEC-Kalender (Typ aus DBV-Grading):")
            print(src[no_bec][["RankingTournamentName", "WeekNr", "Country", "Grading"]].to_string(index=False))
    build_ergaenzung(dbv_lists, bec)


if __name__ == "__main__":
    main()
