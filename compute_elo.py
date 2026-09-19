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

Turnierstaerke nutzt den Rating-STAND VOR dem jeweiligen Turnier (erste Zeile des Spielers in
diesem Turnier, bevor deren erstes Match dort verarbeitet wird), nicht die finalen Ratings nach
dem kompletten Replay -- eine erste Fassung nutzte die finalen Werte (wie
compute_elo_strength.py) und zeigte dadurch einen klaren Rueckschau-Effekt: bei identisch
benannten wiederkehrenden Turnieren (z.B. "Austrian U17 Open" 2025 vs. 2026) fiel der berechnete
Wert 2026 systematisch, obwohl kein Grund zur Annahme bestand, dass dasselbe Turnier real
schwaecher besetzt war (User-Nachfrage 2026-09-18, per Vergleich mehrerer wiederkehrender
Turnierpaare bestaetigt, ~-21 Punkte im Schnitt). Ursache: Teilnehmer frueher (2025er) Turniere
hatten bis zum Ende des Datenbestands (~Sept. 2026) weit mehr Zeit, ihr Rating durch spaetere
Siege zu steigern, was dem fruehen Turnier faelschlich rueckwirkend gutgeschrieben wurde. Die
Spieler-Rangliste (elo_spieler.csv) nutzt weiterhin die finalen Ratings -- das ist dort korrekt,
da sie den AKTUELLEN Stand zeigen soll, nicht einen historischen Zeitpunkt.

Turnierstaerke = Ø-Rating der TOP_N_STRENGTH staerksten Teilnehmer (nicht des kompletten Feldes)
-- User-Nachfrage 2026-09-19, warum GP-Turniere (offizielles BEC-Tier "hoechste Kategorie") in
der Turnierstaerke nicht klar vor IS/IC lagen. Verifiziert per Vergleich mit den offiziellen
BEC-Ranglisten (tournamentsoftware.com rid=187/178): unsere staerksten Spieler laut Elo/Punkte-
Rangliste deckten sich mit den dortigen Top-10 (siehe Session), das Problem lag also nicht an
falschen Matchdaten. Zwei Hypothesen dafuer getestet, warum das reine Feld-Ø die Tiers nicht
trennt:
  1. Cold-Start (fruehe 2025er-Turniere starten alle bei BASE_RATING): per Warmlauf ueber ALLE
     48 Turniere chronologisch ohnehin schon vermieden (pre_tournament-Snapshot nutzt den
     bereits akkumulierten Rating-Stand, auch fuer 2025er-Turniere in der Mitte/am Ende der
     Saison). Test: Beschraenkung der Turnierstaerke-Ausgabe auf ausschliesslich 2026er-Turniere
     (nach 1+ Jahr Warmlauf) zeigte KEINE Verbesserung der Tier-Trennung (GP sogar leicht hinter
     IS) -- verworfen, kein struktureller Fix noetig, da der Warmlauf bereits vorhanden ist.
  2. Feld-Groesse/-Zusammensetzung: `avg_elo` mittelte bisher ueber das KOMPLETTE Meldefeld
     (150-350 Teilnehmer je Turnier), das bei allen Turnieren unabhaengig vom Tier zu einem
     Grossteil aus nicht-elitaeren/neuen Spielern besteht (Korrelation Feldgroesse<->avg_elo
     ueber alle 47 Turniere: r=-0.02, GP hatte sogar die groessten Felder im Schnitt). Das
     BEC-Tier bemisst vermutlich das Niveau der SPITZE eines Turniers (Preisgeld/Prestige), nicht
     das Niveau des kompletten Feldes -- ein Volltfeld-Mittelwert kann diese Tier-Unterschiede
     also strukturell nicht abbilden. Umgestellt auf Top-16-Mittelwert (User-Entscheidung,
     2026-09-19) als naeherungsweises Mass fuer "Staerke der Spitze" statt "Staerke des
     gesamten Feldes". `teilnehmer` bleibt zusaetzlich als Feldgroesse des KOMPLETTEN Feldes in
     der Ausgabe erhalten (Kontext), `teilnehmer_fuer_staerke` zeigt, wie viele Werte tatsaechlich
     in den Top-16-Mittelwert eingeflossen sind (< 16 bei kleineren Feldern).

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
TOP_N_STRENGTH = 16
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
    """Spielt alle Matches chronologisch durch. Neben dem laufenden (finalen) Rating wird pro
    (Turnier, Spieler) ein "Vor-Turnier"-Snapshot festgehalten: der Rating-Stand beim ERSTEN
    Auftreten dieses Spielers in diesem Turnier, bevor das jeweilige Match verarbeitet wird --
    das ist die Grundlage fuer eine rueckschaufreie Turnierstaerke (siehe compute_tournament_
    strength). Matches innerhalb desselben Turniers aendern den Snapshot nicht mehr nachtraeglich."""
    ratings = {}
    match_counts = defaultdict(int)
    pre_tournament = {}  # (turnier_id, spieler_id) -> Rating vor diesem Turnier

    for m in matches:
        heim, gast = m["heim"], m["gast"]
        turnier_id = m["turnier_id"]
        for pid in (heim[0], heim[1], gast[0], gast[1]):
            if pid is not None and (turnier_id, pid) not in pre_tournament:
                pre_tournament[(turnier_id, pid)] = ratings.get(pid, BASE_RATING)

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

    return ratings, match_counts, pre_tournament


def compute_tournament_strength(matches, pre_tournament, top_n=TOP_N_STRENGTH):
    """Ø-Elo der TOP_N_STRENGTH staerksten Teilnehmer je Turnier (nicht des kompletten Feldes),
    JEWEILS zum Rating-Stand vor diesem Turnier (nicht final) -- vermeidet den Rueckschau-Effekt
    frueherer Turniere, die sonst von der spaeteren Formkurve ihrer Teilnehmer profitiert haetten
    (siehe Moduldocstring). Volltfeld-Mittelwert wurde verworfen, da er die BEC-Tiers (GP/IS/IC)
    nicht trennte -- die Tier-Einordnung bemisst sich offenbar an der Spitze eines Turniers, nicht
    am Durchschnitt des gesamten (oft 150-350 Personen grossen) Meldefelds."""
    participants_by_turnier = defaultdict(set)
    for m in matches:
        for pid in (m["heim"][0], m["heim"][1], m["gast"][0], m["gast"][1]):
            if pid is not None:
                participants_by_turnier[m["turnier_id"]].add(pid)

    rows = []
    for turnier_id, spieler_ids in participants_by_turnier.items():
        werte = [pre_tournament[(turnier_id, p)] for p in spieler_ids if (turnier_id, p) in pre_tournament]
        if werte:
            top_werte = sorted(werte, reverse=True)[:top_n]
            rows.append((turnier_id, len(werte), len(top_werte), round(sum(top_werte) / len(top_werte), 1)))
    return rows


def main():
    conn = sqlite3.connect(DB_PATH)
    os.makedirs(OUT_DIR, exist_ok=True)
    try:
        turnier_lookup = pd.read_sql_query(
            """
            SELECT t.turnier_id, t.name, t.jahr, t.kw, t.bec17type, MIN(m.spieldatum) AS datum
            FROM turnier t
            LEFT JOIN matches m ON m.turnier_id = t.turnier_id
            GROUP BY t.turnier_id
            """,
            conn,
        )
        player_lookup = pd.read_sql_query(
            "SELECT spieler_id, vorname, name, nation, bec_player_id FROM player", conn
        )

        all_player_rows = []
        all_strength_rows = []
        for disziplin in DISZIPLINEN:
            matches = load_matches(conn, disziplin)
            ratings, match_counts, pre_tournament = compute_elo_for_disziplin(matches)
            print(f"{disziplin}: {len(matches)} Matches, {len(ratings)} Spieler")

            for spieler_id, rating in ratings.items():
                all_player_rows.append(
                    {
                        "disziplin": disziplin, "spieler_id": spieler_id,
                        "elo": round(rating, 1), "matches": match_counts[spieler_id],
                    }
                )

            for turnier_id, n_teilnehmer, n_fuer_staerke, avg_elo in compute_tournament_strength(matches, pre_tournament):
                all_strength_rows.append(
                    {"disziplin": disziplin, "turnier_id": turnier_id,
                     "teilnehmer": n_teilnehmer, "teilnehmer_fuer_staerke": n_fuer_staerke,
                     "avg_elo": avg_elo}
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
                ["disziplin", "turnier_id", "name", "jahr", "kw", "datum", "bec17type",
                 "teilnehmer", "teilnehmer_fuer_staerke", "avg_elo", "rang"]
            ].to_dict(orient="records"),
            "gesamt": gesamt_df[
                ["turnier_id", "name", "jahr", "kw", "datum", "bec17type", "teilnehmer_gesamt", "n_disziplinen",
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
