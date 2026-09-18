"""
bec_api.py
Gemeinsame Helfer fuer den Zugriff auf die BEC-Datenhub-API (bec-dh-prod.badmintoneurope.com)
und das Upserten von Spielern -- genutzt von fetch_bec_data.py (Matches) und
fetch_bec_entries_winners.py (Entries + Winner-Platzierungen).
"""
import time

import requests

API_BASE = "https://bec-dh-prod.badmintoneurope.com"
HEADERS = {"User-Agent": "bec-u17-auswertung-research/1.0 (privates, nicht-kommerzielles Projekt)"}
REQUEST_DELAY_SECONDS = 0.4

# BEC-eventLabel/eventName-Praefix -> unser Disziplin-Code (siehe schema.sql).
# BEC nutzt fuer U17 die Erwachsenen-Kuerzel MS/WS/MD/WD/XD statt unserer Jugend-Kuerzel
# BS/GS/BD/GD/XD (siehe CLAUDE.md, "BEC-eventLabel-Praefix != unser Disziplin-Code").
EVENT_LABEL_TO_DISZIPLIN = {
    "MS": "BS",
    "WS": "GS",
    "MD": "BD",
    "WD": "GD",
    "XD": "XD",
}


class NoDataAvailable(Exception):
    """BEC-Datenhub kennt dieses Turnier nicht (HTTP 200, aber leerer Body) -- z.B. weil es
    ausserhalb Europas ausgetragen wurde und nicht in BECs eigenem System erfasst ist."""


def get_json(path):
    url = f"{API_BASE}/{path}"
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    if not r.text.strip():
        raise NoDataAvailable(url)
    time.sleep(REQUEST_DELAY_SECONDS)
    return r.json()


def upsert_player(conn, player_json):
    """player_json: dict wie unter team{1,2}.player{1,2} in der BEC-API.
    Gibt unsere interne spieler_id zurueck (Insert-once, kein Update noetig -- BEC liefert
    ueberall dieselben stabilen Stammdaten je playerId)."""
    bec_id = player_json["playerId"]
    row = conn.execute("SELECT spieler_id FROM player WHERE bec_player_id = ?", (bec_id,)).fetchone()
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


def disziplin_from_event_label(event_label):
    """z.B. 'MS U17' -> 'BS'. Gibt None bei unbekanntem Praefix zurueck."""
    prefix = event_label.split()[0]
    return EVENT_LABEL_TO_DISZIPLIN.get(prefix)
