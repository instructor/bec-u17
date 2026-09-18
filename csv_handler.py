"""
csv_handler.py : CSV Handler für Tournament Scraper
Liest tournament-urls.csv und schreibt Ergebnis-CSVs
"""
import csv
import os


def write_players_to_csv(players, csv_file):
    """
    Schreibt Spieler in CSV (ohne URL-Zeile, für einzelne Turnier-Dateien)
    """
    try:
        with open(csv_file, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f, delimiter=';')

            # Header
            writer.writerow(['name', 'vorname', 'club', 'nation'])

            # Spieler schreiben
            for i, player in enumerate(players, start=1):
                try:
                    writer.writerow([
                        player.get('name', ''),
                        player.get('vorname', ''),
                        player.get('club', ''),
                        player.get('nation', '')
                    ])
                except Exception as e:
                    print(f"⚠️ Fehler bei Spieler {i}: {player} → {e}")

        print(f"✓ {len(players)} Spieler in {csv_file} geschrieben")

    except Exception as e:
        print(f"✗ Fehler beim Schreiben in {csv_file}: {e}")


def extract_tournament_id(url):
    """
    Extrahiert die Tournament-ID aus der URL

    Args:
        url: Tournament-URL

    Returns:
        Tournament-ID (uppercase) oder None
    """
    import re

    # Pattern: /tournament/{ID} oder ?id={ID}
    patterns = [
        r'/tournament/([A-F0-9-]+)',
        r'[?&]id=([A-F0-9-]+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, url, re.IGNORECASE)
        if match:
            return match.group(1).upper()

    return None


def read_tournaments_from_csv(csv_file):
    """
    Liest Turniere aus CSV-Datei

    Args:
        csv_file: Pfad zur CSV-Datei

    Returns:
        Liste von Dicts mit 'turnier_name', 'abbreviation', 'url'
    """
    tournaments = []

    try:
        if not os.path.exists(csv_file):
            print(f"✗ Datei nicht gefunden: {csv_file}")
            return []

        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')

            for row in reader:
                use_it = row.get('use_it', '').strip().lower()
                url = row.get('url', '').strip()

                # Nur Zeilen mit use_it='x' verarbeiten
                if use_it == 'x' and url:
                    tournaments.append({
                        'turnier_name': row.get('turnier_name', '').strip(),
                        'abbreviation': row.get('abbreviation', '').strip(),
                        'url': url
                    })

        print(f"✓ {len(tournaments)} Turniere aus {csv_file} geladen")
        return tournaments

    except Exception as e:
        print(f"✗ Fehler beim Lesen von {csv_file}: {e}")
        return []


def read_players_from_csv(players_csv):
    players = []
    if not os.path.exists(players_csv):
        return players
    with open(players_csv, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            players.append({
                "name": row.get("name", "").strip(),
                "vorname": row.get("vorname", "").strip(),
                "club": row.get("club", "").strip(),
                "nation": row.get("nation", "").strip()
            })
    return players
