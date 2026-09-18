"""
compute_elo.py
Phase 4: Elo-Rangliste je Disziplin + Turnierstaerke (Ø-Elo der Teilnehmer) -- analog
../bec_u15_auswertung/compute_elo_strength.py, aber:
  - je Disziplin (BS/GS/BD/GD/XD) statt nur je Geschlecht (unser matches-Schema trennt bereits so)
  - Doppel/Mixed (BD/GD/XD): Team-Rating = Mittelwert der Partner-Ratings, Delta wird beiden
    Partnern identisch gutgeschrieben (Konvention aus dem BRAIN-Projekt, siehe
    ../CLAUDE.md/build_elo_ranking.py)
  - chronologisch sortiert nach matches.spieldatum (+ match_id als stabiler Tie-Breaker),
    nicht nach DB-Einfuegereihenfolge

Bekannte Vereinfachung (bewusst uebernommen von compute_elo_strength.py): Turnierstaerke nutzt
die FINALEN Ratings nach dem kompletten Replay, nicht den Rating-Stand zum jeweiligen
Turnierzeitpunkt -- fuer fruehe Turniere dadurch ein gewisser Rueckschau-Effekt, wie beim
U15-Vorbild nicht weiter behoben.

Walkover-Matches ohne vollstaendige Spielerdaten (leeres ergebnis, eine Seite komplett NULL)
werden uebersprungen -- kein echtes Staerke-Signal, keine ID zum Aktualisieren.
"""
import os
import sqlite3
from collections import defaultdict

import pandas as pd

DB_PATH = "u17_int.db"
OUT_DIR = "_RESULTS"
BASE_RATING = 1200
K_FACTOR = 32
DISZIPLINEN = ["BS", "GS", "BD", "GD", "XD"]
DOUBLES = {"BD", "GD", "XD"}


def expected_score(r_a, r_b):
    return 1 / (1 + 10 ** ((r_b - r_a) / 400))


def update_elo(r_a, r_b, score_a, k=K_FACTOR):
    return r_a + k * (score_a - expected_score(r_a, r_b))


def load_matches(conn, disziplin):
    rows = conn.execute(
        """
        SELECT match_id, turnier_id, spieldatum,
               heim_spieler1_id, heim_spieler2_id, gast_spieler1_id, gast_spieler2_id, winner_seite
        FROM matches
        WHERE disziplin = ?
        ORDER BY spieldatum, match_id
        """,
        (disziplin,),
    ).fetchall()

    matches = []
    for match_id, turnier_id, spieldatum, h1, h2, g1, g2, winner_seite in rows:
        if h1 is None or g1 is None:
            continue  # Walkover ohne vollstaendige Spielerdaten -- kein Staerke-Signal
        matches.append(
            {
                "match_id": match_id, "turnier_id": turnier_id,
                "heim": (h1, h2), "gast": (g1, g2),
                "heim_win": winner_seite == "heim",
            }
        )
    return matches


def team_rating(ratings, team):
    p1, p2 = team
    if p2 is None:
        return ratings.setdefault(p1, BASE_RATING)
    r1 = ratings.setdefault(p1, BASE_RATING)
    r2 = ratings.setdefault(p2, BASE_RATING)
    return (r1 + r2) / 2


def apply_delta(ratings, team, delta):
    p1, p2 = team
    ratings[p1] = ratings[p1] + delta
    if p2 is not None:
        ratings[p2] = ratings[p2] + delta


def compute_elo_for_disziplin(matches):
    ratings = {}
    match_counts = defaultdict(int)

    for m in matches:
        heim, gast = m["heim"], m["gast"]
        r_heim = team_rating(ratings, heim)
        r_gast = team_rating(ratings, gast)
        score_heim = 1.0 if m["heim_win"] else 0.0

        delta_heim = K_FACTOR * (score_heim - expected_score(r_heim, r_gast))
        delta_gast = K_FACTOR * ((1 - score_heim) - expected_score(r_gast, r_heim))
        apply_delta(ratings, heim, delta_heim)
        apply_delta(ratings, gast, delta_gast)

        for pid in (heim[0], heim[1], gast[0], gast[1]):
            if pid is not None:
                match_counts[pid] += 1

    return ratings, match_counts


def compute_tournament_strength(matches, ratings):
    """Ø-Elo aller Teilnehmer je Turnier (Teilnehmer = alle Spieler, die mind. 1 Match in
    diesem Turnier/dieser Disziplin bestritten haben)."""
    participants_by_turnier = defaultdict(set)
    for m in matches:
        for pid in (m["heim"][0], m["heim"][1], m["gast"][0], m["gast"][1]):
            if pid is not None:
                participants_by_turnier[m["turnier_id"]].add(pid)

    rows = []
    for turnier_id, spieler_ids in participants_by_turnier.items():
        werte = [ratings[p] for p in spieler_ids if p in ratings]
        if werte:
            rows.append((turnier_id, len(werte), round(sum(werte) / len(werte), 1)))
    return rows


def main():
    conn = sqlite3.connect(DB_PATH)
    os.makedirs(OUT_DIR, exist_ok=True)
    try:
        turnier_lookup = pd.read_sql_query(
            "SELECT turnier_id, name, jahr, kw, bec17type FROM turnier", conn
        )
        player_lookup = pd.read_sql_query(
            "SELECT spieler_id, vorname, name, nation, bec_player_id FROM player", conn
        )

        all_player_rows = []
        all_strength_rows = []
        for disziplin in DISZIPLINEN:
            matches = load_matches(conn, disziplin)
            ratings, match_counts = compute_elo_for_disziplin(matches)
            print(f"{disziplin}: {len(matches)} Matches, {len(ratings)} Spieler")

            for spieler_id, rating in ratings.items():
                all_player_rows.append(
                    {
                        "disziplin": disziplin, "spieler_id": spieler_id,
                        "elo": round(rating, 1), "matches": match_counts[spieler_id],
                    }
                )

            for turnier_id, n_teilnehmer, avg_elo in compute_tournament_strength(matches, ratings):
                all_strength_rows.append(
                    {"disziplin": disziplin, "turnier_id": turnier_id,
                     "teilnehmer": n_teilnehmer, "avg_elo": avg_elo}
                )

        player_df = pd.DataFrame(all_player_rows).merge(player_lookup, on="spieler_id", how="left")
        player_df["rang"] = player_df.groupby("disziplin")["elo"].rank(ascending=False, method="dense").astype(int)
        player_df = player_df.sort_values(["disziplin", "rang"])
        player_path = os.path.join(OUT_DIR, "elo_spieler.csv")
        player_df.to_csv(player_path, index=False, encoding="utf-8-sig", sep=";")
        print(f"-> {player_path} ({len(player_df)} Zeilen)")

        strength_df = pd.DataFrame(all_strength_rows).merge(turnier_lookup, on="turnier_id", how="left")
        strength_df["rang"] = strength_df.groupby("disziplin")["avg_elo"].rank(ascending=False, method="dense").astype(int)
        strength_df = strength_df.sort_values(["disziplin", "rang"])
        strength_path = os.path.join(OUT_DIR, "turnier_staerke.csv")
        strength_df.to_csv(strength_path, index=False, encoding="utf-8-sig", sep=";")
        print(f"-> {strength_path} ({len(strength_df)} Zeilen)")

        # Gesamt/gemittelt je Turnier: unbenutzt gewichteter Mittelwert ueber die Disziplinen, in
        # denen das Turnier ueberhaupt Daten hat (nicht jedes Turnier hat alle 5 Disziplinen --
        # z.B. European Youth Olympic Festival 2025 nur MS/WS/XD, siehe CLAUDE.md).
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
        gesamt_df = gesamt_df.merge(turnier_lookup, on="turnier_id", how="left")
        gesamt_df["rang"] = gesamt_df["avg_elo_gesamt"].rank(ascending=False, method="dense").astype(int)
        gesamt_df = gesamt_df.sort_values("rang")
        gesamt_path = os.path.join(OUT_DIR, "turnier_staerke_gesamt.csv")
        gesamt_df.to_csv(gesamt_path, index=False, encoding="utf-8-sig", sep=";")
        print(f"-> {gesamt_path} ({len(gesamt_df)} Zeilen)")

        # Kombiniertes JSON fuer die Web-Visualisierung (je Disziplin + Gesamt, inkl. Tier)
        json_path = os.path.join(OUT_DIR, "turnier_staerke.json")
        payload = {
            "je_disziplin": strength_df[
                ["disziplin", "turnier_id", "name", "jahr", "kw", "bec17type", "teilnehmer", "avg_elo", "rang"]
            ].to_dict(orient="records"),
            "gesamt": gesamt_df[
                ["turnier_id", "name", "jahr", "kw", "bec17type", "teilnehmer_gesamt", "n_disziplinen",
                 "avg_elo_gesamt", "rang"]
            ].to_dict(orient="records"),
        }
        import json
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"-> {json_path}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
