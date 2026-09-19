"""
compute_official_strength.py
Zweiter, von compute_elo.py UNABHAENGIGER Ansatz fuer die Turnierstaerke (User-Wunsch
2026-09-19, parallel zur Elo-Methode): statt Spielstaerke aus unseren eigenen 8.884 Matches
abzuleiten, nutzt dieser Ansatz die offizielle "BEC U17 Circuit Ranking"-Punktzahl jedes Spielers
(fetch_official_ranking.py, tournamentsoftware.com rid=187) als externes, unabhaengiges
Staerkemass: ein Turnier ist stark, wenn viele hoch platzierte Spieler laut offizieller
Rangliste teilgenommen haben.

Turnierstaerke_offiziell = Oe-Punkte der TOP_N_STRENGTH staerksten (laut offizieller Rangliste)
Teilnehmer je Turnier -- gleiche Top-N-Logik wie compute_elo.py (aus dem gleichen Grund: ein
Volltfeld-Mittelwert wuerde von den vielen nicht offiziell gerankten/schwaecheren Teilnehmern
verwaesserst, siehe dortige Begruendung). Teilnehmer ohne Eintrag in der offiziellen Rangliste
(z.B. zu neu/nicht auf dem Circuit aktiv) gehen mit 0 Punkten ein.

Im Unterschied zur Elo-Methode ist die offizielle Rangliste NICHT zeitpunktbezogen -- sie ist ein
aktueller Schnappschuss (Stand der zuletzt geladenen Ranking-Woche) und fliesst hier fuer JEDES
Turnier im gleichen (aktuellen) Stand ein, unabhaengig vom Turnierdatum. Das ist ein bewusster
Kompromiss: die offizielle Rangliste hat keine rueckwirkend abrufbare Historie je Kalenderwoche
in unserem Zugriff, im Gegensatz zu unserer eigenen chronologischen Elo-Berechnung.

Teilnahmequelle: `entries` (wie compute_elo.py/export_spielerrangliste.py).
"""
import json
import os
import sqlite3
from collections import defaultdict

DB_PATH = "u17_int.db"
OUT_DIR = "_RESULTS"
DISZIPLINEN = ["BS", "GS", "BD", "GD", "XD"]
TOP_N_STRENGTH = 16


def load_official_points(disziplin):
    """bec_member_id -> (rang, punkte) laut offizieller BEC-Rangliste."""
    path = os.path.join(OUT_DIR, f"offizielle_rangliste_{disziplin}.csv")
    import csv
    out = {}
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f, delimiter=";"):
            out[row["member_id"]] = (int(row["rang"]), int(row["punkte"]))
    return out


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    os.makedirs(OUT_DIR, exist_ok=True)

    turnier_lookup = {
        r["turnier_id"]: dict(r)
        for r in conn.execute(
            """
            SELECT t.turnier_id, t.name, t.jahr, t.kw, t.bec17type, MIN(m.spieldatum) AS datum
            FROM turnier t
            LEFT JOIN matches m ON m.turnier_id = t.turnier_id
            GROUP BY t.turnier_id
            """
        ).fetchall()
    }

    all_strength_rows = []
    for disziplin in DISZIPLINEN:
        official = load_official_points(disziplin)

        entries = conn.execute(
            "SELECT turnier_id, spieler1_id, spieler2_id FROM entries WHERE disziplin = ?", (disziplin,)
        ).fetchall()

        member_id_by_spieler = {
            r["spieler_id"]: r["bec_member_id"] for r in conn.execute("SELECT spieler_id, bec_member_id FROM player")
        }

        participants_by_turnier = defaultdict(set)
        for e in entries:
            for spieler_id in (e["spieler1_id"], e["spieler2_id"]):
                if spieler_id is not None:
                    participants_by_turnier[e["turnier_id"]].add(spieler_id)

        n_turniere = 0
        for turnier_id, spieler_ids in participants_by_turnier.items():
            punkte_liste = []
            for spieler_id in spieler_ids:
                member_id = member_id_by_spieler.get(spieler_id)
                _, punkte = official.get(member_id, (None, 0))
                punkte_liste.append(punkte)
            punkte_liste.sort(reverse=True)
            top = punkte_liste[:TOP_N_STRENGTH]
            n_bekannt = sum(1 for p in top if p > 0)
            avg_punkte = round(sum(top) / len(top), 1) if top else 0.0
            all_strength_rows.append(
                {
                    "disziplin": disziplin, "turnier_id": turnier_id,
                    "teilnehmer": len(spieler_ids), "teilnehmer_fuer_staerke": len(top),
                    "teilnehmer_offiziell_gerankt": n_bekannt,
                    "avg_elo": avg_punkte,  # gleicher Feldname wie turnier_staerke.json, fuers Wiederverwenden der Web-Seite
                }
            )
            n_turniere += 1
        print(f"{disziplin}: {n_turniere} Turniere, {len(official)} offiziell gerankte Spieler geladen")

    import pandas as pd

    strength_df = pd.DataFrame(all_strength_rows).merge(
        pd.DataFrame(turnier_lookup.values()), on="turnier_id", how="left"
    )
    strength_df["rang"] = strength_df.groupby("disziplin")["avg_elo"].rank(ascending=False, method="dense").astype(int)
    strength_df = strength_df.sort_values(["disziplin", "rang"])
    strength_path = os.path.join(OUT_DIR, "turnier_staerke_offiziell.csv")
    strength_df.to_csv(strength_path, index=False, encoding="utf-8-sig", sep=";")
    print(f"-> {strength_path} ({len(strength_df)} Zeilen)")

    gesamt_df = (
        strength_df.groupby("turnier_id")
        .agg(
            avg_elo_gesamt=("avg_elo", "mean"),
            teilnehmer_gesamt=("teilnehmer", "sum"),
            n_disziplinen=("disziplin", "nunique"),
        )
        .reset_index()
    )
    gesamt_df["avg_elo_gesamt"] = gesamt_df["avg_elo_gesamt"].round(1)
    gesamt_df = gesamt_df.merge(pd.DataFrame(turnier_lookup.values()), on="turnier_id", how="left")
    gesamt_df["rang"] = gesamt_df["avg_elo_gesamt"].rank(ascending=False, method="dense").astype(int)
    gesamt_df = gesamt_df.sort_values("rang")
    gesamt_path = os.path.join(OUT_DIR, "turnier_staerke_offiziell_gesamt.csv")
    gesamt_df.to_csv(gesamt_path, index=False, encoding="utf-8-sig", sep=";")
    print(f"-> {gesamt_path} ({len(gesamt_df)} Zeilen)")

    json_path = os.path.join(OUT_DIR, "turnier_staerke_offiziell.json")
    payload = {
        "je_disziplin": strength_df[
            ["disziplin", "turnier_id", "name", "jahr", "kw", "datum", "bec17type",
             "teilnehmer", "teilnehmer_fuer_staerke", "teilnehmer_offiziell_gerankt", "avg_elo", "rang"]
        ].to_dict(orient="records"),
        "gesamt": gesamt_df[
            ["turnier_id", "name", "jahr", "kw", "datum", "bec17type", "teilnehmer_gesamt", "n_disziplinen",
             "avg_elo_gesamt", "rang"]
        ].to_dict(orient="records"),
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    print(f"-> {json_path}")


if __name__ == "__main__":
    main()
