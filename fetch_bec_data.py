"""
fetch_bec_data.py
Phase 2: laedt Spieler + Matches aller Turniere aus der "turnier"-Tabelle direkt von der
BEC-Datenhub-API (bec-dh-prod.badmintoneurope.com), kein Browser noetig.

Pro Turnier:
  1. GET /tournament/{code}            -> startDate/endDate zur Bestimmung der Turniertage
  2. GET /tournament/{code}/matches/{date}  fuer jeden Tag im Datumsbereich
  3. Spieler (bec_player_id-basiert) + Matches in die DB upserten
  4. turnier.scraped_at setzen (resumable: --no-resume erzwingt Neuabruf)

Nur Matches mit matchState == "F" (finished, mit gesetztem winner) werden importiert.
"""
import argparse
import datetime as dt
import sqlite3
import time

import requests

DB_PATH = "u17_int.db"
API_BASE = "https://bec-dh-prod.badmintoneurope.com"
HEADERS = {"User-Agent": "bec-u17-auswertung-research/1.0 (privates, nicht-kommerzielles Projekt)"}
REQUEST_DELAY_SECONDS = 0.4

# BEC-eventLabel-Praefix -> unser Disziplin-Code (siehe schema.sql)
EVENT_LABEL_TO_DISZIPLIN = {
    "MS": "BS",
    "WS": "GS",
    "MD": "BD",
    "WD": "GD",
    "XD": "XD",
}


def get_json(path, params=None):
    url = f"{API_BASE}/{path}"
    r = requests.get(url, headers=HEADERS, params=params, timeout=20)
    r.raise_for_status()
    return r.json()


def daterange(start_date, end_date):
    d = start_date
    while d <= end_date:
        yield d
        d += dt.timedelta(days=1)


def parse_iso_date(s):
    return dt.date.fromisoformat(s[:10])


def upsert_player(conn, player_json):
    """player_json: dict wie unter team{1,2}.player{1,2} in der Matches-API.
    Gibt unsere interne spieler_id zurueck (INSERT OR IGNORE + SELECT, kein Update noetig --
    BEC liefert bei jedem Match dieselben stabilen Stammdaten)."""
    bec_id = player_json["playerId"]
    cur = conn.execute("SELECT spieler_id FROM player WHERE bec_player_id = ?", (bec_id,))
    row = cur.fetchone()
    if row:
        return row[0]

    gender = "M" if player_json.get("genderId") == 1 else ("W" if player_json.get("genderId") == 2 else None)
    cur = conn.execute(
        """
        INSERT INTO player (bec_player_id, bec_member_id, name, vorname, gender, nation)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            bec_id,
            player_json.get("memberId"),
            player_json.get("lastName"),
            player_json.get("firstName"),
            gender,
            player_json.get("countryCode"),
        ),
    )
    return cur.lastrowid


def upsert_team(conn, team_json):
    """Gibt (spieler1_id, spieler2_id) zurueck; spieler2_id bleibt None bei Einzel."""
    p1 = upsert_player(conn, team_json["player1"]) if team_json.get("player1") else None
    p2 = upsert_player(conn, team_json["player2"]) if team_json.get("player2") else None
    return p1, p2


def format_ergebnis(games):
    sets = [f"{g['team1Result']}-{g['team2Result']}" for g in games if g.get("team1Result") is not None]
    return " ".join(sets)


def import_match(conn, turnier_id, match_json):
    if match_json.get("matchState") != "F" or match_json.get("winner") not in (1, 2):
        return False  # nicht gespielt / kein Endergebnis -- ueberspringen

    event_label = match_json["eventLabel"]  # z.B. "MS U17"
    prefix = event_label.split()[0]
    disziplin = EVENT_LABEL_TO_DISZIPLIN.get(prefix)
    if disziplin is None:
        print(f"    WARNUNG: unbekanntes eventLabel {event_label!r}, Match uebersprungen")
        return False

    heim1, heim2 = upsert_team(conn, match_json["team1"])
    gast1, gast2 = upsert_team(conn, match_json["team2"])
    ergebnis = format_ergebnis(match_json.get("games") or [])
    winner_seite = "heim" if match_json["winner"] == 1 else "gast"

    conn.execute(
        """
        INSERT INTO matches (
            bec_match_id, turnier_id, disziplin, runde,
            heim_spieler1_id, heim_spieler2_id, gast_spieler1_id, gast_spieler2_id,
            ergebnis, winner_seite
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(bec_match_id) DO UPDATE SET
            disziplin = excluded.disziplin,
            runde = excluded.runde,
            heim_spieler1_id = excluded.heim_spieler1_id,
            heim_spieler2_id = excluded.heim_spieler2_id,
            gast_spieler1_id = excluded.gast_spieler1_id,
            gast_spieler2_id = excluded.gast_spieler2_id,
            ergebnis = excluded.ergebnis,
            winner_seite = excluded.winner_seite
        """,
        (
            match_json["id"], turnier_id, disziplin, match_json.get("roundName"),
            heim1, heim2, gast1, gast2, ergebnis, winner_seite,
        ),
    )
    return True


def fetch_tournament(conn, turnier_id, tournament_code, name):
    print(f"\n=== {name} ({tournament_code}) ===")
    meta = get_json(f"tournament/{tournament_code}")
    time.sleep(REQUEST_DELAY_SECONDS)
    start_date = parse_iso_date(meta["startDate"])
    end_date = parse_iso_date(meta["endDate"])

    total_matches = 0
    for day in daterange(start_date, end_date):
        blocks = get_json(f"tournament/{tournament_code}/matches/{day.isoformat()}")
        time.sleep(REQUEST_DELAY_SECONDS)
        day_matches = 0
        for block in blocks:
            for m in block.get("matches") or []:
                if import_match(conn, turnier_id, m):
                    day_matches += 1
        if day_matches:
            print(f"  {day.isoformat()}: {day_matches} Matches importiert")
        total_matches += day_matches

    conn.execute(
        "UPDATE turnier SET scraped_at = ? WHERE turnier_id = ?",
        (dt.datetime.now().isoformat(timespec="seconds"), turnier_id),
    )
    conn.commit()
    print(f"  -> {total_matches} Matches gesamt")
    return total_matches


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-resume", action="store_true", help="auch bereits gescrapete Turniere erneut abrufen")
    ap.add_argument("--limit", type=int, default=None, help="nur die ersten N (noch offenen) Turniere verarbeiten")
    args = ap.parse_args()

    conn = sqlite3.connect(DB_PATH)
    try:
        query = "SELECT turnier_id, tournament_code, name FROM turnier"
        if not args.no_resume:
            query += " WHERE scraped_at IS NULL"
        query += " ORDER BY jahr, kw"
        rows = conn.execute(query).fetchall()
        if args.limit:
            rows = rows[: args.limit]

        print(f"{len(rows)} Turniere zu verarbeiten (resume={'aus' if args.no_resume else 'an'}).")
        grand_total = 0
        errors = []
        for turnier_id, code, name in rows:
            try:
                grand_total += fetch_tournament(conn, turnier_id, code, name)
            except Exception as e:
                print(f"  FEHLER bei {name} ({code}): {e}")
                errors.append((name, code, str(e)))

        print(f"\nFertig. {grand_total} Matches importiert insgesamt, {len(errors)} Fehler.")
        for name, code, err in errors:
            print(f"  - {name} ({code}): {err}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
