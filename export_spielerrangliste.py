"""
export_spielerrangliste.py
Exportiert _RESULTS/spielerrangliste.json fuer die Web-Rangliste (web/spielerrangliste.html):
je Disziplin eine Spielerliste (sortiert nach Elo-Rang, mit Punkte-Rangliste als Zweitinfo) plus
die von jedem Spieler gespielten Turniere (Name, Datum, Tier, Link, Stern bei Top-3-Turnierstaerke
dieser Disziplin -- siehe compute_elo.py/turnier_staerke.json, User-Entscheidung 2026-09-19).

Turnierdetails werden je Disziplin EINMAL in einer Lookup-Tabelle abgelegt, Spieler referenzieren
nur turnier_id -- vermeidet, Name/Datum/Tier pro Spieler zu duplizieren (mehrere hundert Spieler
je Turnier).

Teilnahmequelle: `entries` (Teilnehmerliste je Turnier/Disziplin aus der ersten Draw-Runde, siehe
schema.sql) -- vollstaendiger als `matches`, da auch Teilnehmer mit reinen Walkover-Ausgaengen
erfasst sind. Bei Doppel/Mixed erzeugt ein Entry-Datensatz eine Teilnahme fuer JEDEN Partner
einzeln (wie rangliste/elo_spieler, die beiden Partnern individuell Punkte/Elo gutschreiben).
"""
import json
import os
import sqlite3

DB_PATH = "u17_int.db"
OUT_DIR = "_RESULTS"
DISZIPLINEN = ["BS", "GS", "BD", "GD", "XD"]
TOURNAMENT_URL = "https://badmintoneurope.com/web/corporate/tournament?tournament_code={code}"


def load_strength_top3(disziplin):
    """turnier_id -> staerke_rang, nur fuer Turniere mit Top-16-Turnierstaerke-Rang <= 3."""
    with open(os.path.join(OUT_DIR, "turnier_staerke.json"), encoding="utf-8") as f:
        staerke = json.load(f)
    return {
        r["turnier_id"]: r["rang"]
        for r in staerke["je_disziplin"]
        if r["disziplin"] == disziplin and r["rang"] <= 3
    }


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    os.makedirs(OUT_DIR, exist_ok=True)

    elo_by_key = {}
    with open(os.path.join(OUT_DIR, "elo_spieler.csv"), encoding="utf-8-sig") as f:
        import csv
        for row in csv.DictReader(f, delimiter=";"):
            elo_by_key[(row["disziplin"], int(row["spieler_id"]))] = {
                "elo": round(float(row["elo"]), 1), "elo_rang": int(row["rang"]), "elo_matches": int(row["matches"]),
            }

    punkte_by_key = {}
    for disziplin in DISZIPLINEN:
        path = os.path.join(OUT_DIR, f"rangliste_{disziplin}.csv")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8-sig") as f:
            import csv
            for i, row in enumerate(csv.DictReader(f, delimiter=";"), start=1):
                pid = conn.execute(
                    "SELECT spieler_id FROM player WHERE bec_player_id = ?", (row["bec_player_id"],)
                ).fetchone()
                if pid is None:
                    continue
                punkte_by_key[(disziplin, pid["spieler_id"])] = {
                    "punkte": int(row["punkte"]), "punkte_rang": int(row["rang"]),
                    "anzahl_turniere": int(row["anzahl_turniere"]),
                }

    disziplinen_out = {}
    for disziplin in DISZIPLINEN:
        top3 = load_strength_top3(disziplin)

        entries = conn.execute(
            "SELECT turnier_id, spieler1_id, spieler2_id FROM entries WHERE disziplin = ?",
            (disziplin,),
        ).fetchall()

        turnier_ids = {e["turnier_id"] for e in entries}
        turnier_lookup = {}
        if turnier_ids:
            qmarks = ",".join("?" * len(turnier_ids))
            rows = conn.execute(
                f"""
                SELECT t.turnier_id, t.name, t.jahr, t.kw, t.bec17type, t.tournament_code,
                       MIN(m.spieldatum) AS datum
                FROM turnier t
                LEFT JOIN matches m ON m.turnier_id = t.turnier_id
                WHERE t.turnier_id IN ({qmarks})
                GROUP BY t.turnier_id
                """,
                tuple(turnier_ids),
            ).fetchall()
            for r in rows:
                turnier_lookup[r["turnier_id"]] = {
                    "name": r["name"], "jahr": r["jahr"], "kw": r["kw"], "bec17type": r["bec17type"],
                    "datum": r["datum"],
                    "url": TOURNAMENT_URL.format(code=r["tournament_code"]),
                    "top3": r["turnier_id"] in top3,
                    "staerke_rang": top3.get(r["turnier_id"]),
                }

        teilnahmen_by_spieler = {}
        for e in entries:
            for spieler_id in (e["spieler1_id"], e["spieler2_id"]):
                if spieler_id is None:
                    continue
                teilnahmen_by_spieler.setdefault(spieler_id, set()).add(e["turnier_id"])

        spieler_out = []
        for spieler_id, turnier_id_set in teilnahmen_by_spieler.items():
            elo_info = elo_by_key.get((disziplin, spieler_id))
            punkte_info = punkte_by_key.get((disziplin, spieler_id))
            if elo_info is None and punkte_info is None:
                continue  # kein Match/keine Platzierung erfasst -- kein Ranking-Eintrag moeglich
            p = conn.execute(
                "SELECT vorname, name, nation, bec_player_id FROM player WHERE spieler_id = ?", (spieler_id,)
            ).fetchone()
            turniere_sorted = sorted(
                turnier_id_set,
                key=lambda tid: turnier_lookup.get(tid, {}).get("datum") or "",
            )
            entry = {
                "spieler_id": spieler_id,
                "vorname": p["vorname"], "name": p["name"], "nation": p["nation"],
                "bec_player_id": p["bec_player_id"],
                "turniere": turniere_sorted,
            }
            entry.update(elo_info or {"elo": None, "elo_rang": None, "elo_matches": 0})
            entry.update(punkte_info or {"punkte": None, "punkte_rang": None, "anzahl_turniere": len(turnier_id_set)})
            spieler_out.append(entry)

        spieler_out.sort(key=lambda r: (r["elo_rang"] is None, r["elo_rang"] if r["elo_rang"] is not None else 0))

        disziplinen_out[disziplin] = {
            "turniere": {str(tid): v for tid, v in turnier_lookup.items()},
            "spieler": spieler_out,
        }
        print(f"{disziplin}: {len(spieler_out)} Spieler, {len(turnier_lookup)} Turniere")

    out_path = os.path.join(OUT_DIR, "spielerrangliste.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"disziplinen": disziplinen_out}, f, ensure_ascii=False, separators=(",", ":"))
    size_kb = os.path.getsize(out_path) / 1024
    print(f"-> {out_path} ({size_kb:.0f} KB)")


if __name__ == "__main__":
    main()
