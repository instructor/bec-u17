"""
fetch_bec_entries_winners.py
Laedt Teilnehmerlisten (entries) und Platzierungen 1/2/3 (turnier_ergebnisse) aller Turniere
aus der "turnier"-Tabelle von der BEC-Datenhub-API -- Ergaenzung zu fetch_bec_data.py (Matches).

Pro Turnier, pro Disziplin (events-Endpunkt):
  1. GET /tournament/{code}/draw/{eventCode}
  2. Entries: erste Draw-Runde (hoechste "col"-Nummer) -> alle Teilnehmer mit Setzung
  3. Platzierungen: JEDE Draw-Runde -> Platz 1 (Champion), Platz 2 (Finalist), Platz 3 (beide
     HF-Verlierer, klassische Kampflos-freie Bronze-Regel im BEC-Circuit -- kein Spiel um Platz 3),
     Platz 5 (4x VF-Verlierer), Platz 9 (8x R16-Verlierer), Platz 17/33/... usw. -- siehe
     import_placements() fuer die genaue Tiegroup-Formel.

Nur Turniere mit Einzel-KO-Draw (tournamentEliminationDrawDTO) werden unterstuetzt; Turniere mit
reinem Gruppensystem (tournamentRoundRobinDrawDTO) werden uebersprungen und geloggt (noch nicht
beobachtet im BEC-U17-Circuit, aber vorsorglich abgefangen statt zum Absturz zu fuehren).

Resumable ueber turnier.entries_scraped_at (--no-resume erzwingt Neuabruf).
"""
import argparse
import datetime as dt
import sqlite3

from bec_api import NoDataAvailable, disziplin_from_event_label, get_json, upsert_team

DB_PATH = "u17_int.db"


def import_entries(conn, turnier_id, disziplin, first_col):
    conn.execute("DELETE FROM entries WHERE turnier_id = ? AND disziplin = ?", (turnier_id, disziplin))
    n = 0
    for row in first_col["drawRowsSorted"]:
        m = row.get("match")
        if not m:
            continue
        for team in (m.get("team1"), m.get("team2")):
            if not team or not team.get("player1"):
                continue
            p1, p2 = upsert_team(conn, team)
            conn.execute(
                "INSERT INTO entries (turnier_id, disziplin, spieler1_id, spieler2_id, seed) VALUES (?, ?, ?, ?, ?)",
                (turnier_id, disziplin, p1, p2, team.get("seed")),
            )
            n += 1
    return n


def import_placements(conn, turnier_id, disziplin, cols_by_col):
    """Platzierung fuer JEDE Draw-Runde, nicht nur Final/Halbfinale: die Verlierer einer Runde
    mit Spalte "col" (1=Final, 2=Halbfinale, 3=Viertelfinale, ...) bilden eine Platzierungs-
    Tiegroup ab Platz 2**(col-1)+1 (Final-Verlierer=2, HF-Verlierer=3/4, VF-Verlierer=5-8,
    R16-Verlierer=9-16, R32-Verlierer=17-32, R64-Verlierer=33-64, ...) -- Standard-KO-Konvention,
    dieselbe wie beim DBV-RP_KT1-Punktetabellen-Schema im BRAIN-Projekt. Noetig fuer eine
    Punkte-Rangliste (Phase 3): nur Platz 1-3 zu erfassen (frueherer Stand) haette die grosse
    Mehrheit der Teilnehmer (alle vor dem Halbfinale ausgeschiedenen) komplett punktelos gelassen.
    """
    conn.execute("DELETE FROM turnier_ergebnisse WHERE turnier_id = ? AND disziplin = ?", (turnier_id, disziplin))
    n = 0

    final_col = cols_by_col.get(1)
    if not final_col or not final_col["drawRowsSorted"]:
        return 0
    final_match = final_col["drawRowsSorted"][0].get("match")
    if not final_match or final_match.get("winner") not in (1, 2):
        return 0  # Final noch nicht gespielt (Turnier evtl. noch offen/abgesagt)

    def insert(team, platz):
        nonlocal n
        if not team or not team.get("player1"):
            return
        p1, p2 = upsert_team(conn, team)
        conn.execute(
            "INSERT INTO turnier_ergebnisse (turnier_id, disziplin, spieler1_id, spieler2_id, platzierung) "
            "VALUES (?, ?, ?, ?, ?)",
            (turnier_id, disziplin, p1, p2, platz),
        )
        n += 1

    win_team = final_match["team1"] if final_match["winner"] == 1 else final_match["team2"]
    lose_team = final_match["team2"] if final_match["winner"] == 1 else final_match["team1"]
    insert(win_team, 1)
    insert(lose_team, 2)

    for col_num, col in cols_by_col.items():
        if col_num == 1:
            continue  # Final bereits oben behandelt (Platz 1+2)
        platz = 2 ** (col_num - 1) + 1  # Start der Platzierungs-Tiegroup dieser Runde
        for row in col["drawRowsSorted"]:
            m = row.get("match")
            if not m or m.get("winner") not in (1, 2):
                continue
            lose_team = m["team2"] if m["winner"] == 1 else m["team1"]
            insert(lose_team, platz)

    return n


def mark_scraped(conn, turnier_id):
    conn.execute(
        "UPDATE turnier SET entries_scraped_at = ? WHERE turnier_id = ?",
        (dt.datetime.now().isoformat(timespec="seconds"), turnier_id),
    )
    conn.commit()


def fetch_tournament(conn, turnier_id, tournament_code, name):
    print(f"\n=== {name} ({tournament_code}) ===")
    try:
        events = get_json(f"tournament/{tournament_code}/events")
    except NoDataAvailable:
        print("  KEINE BEC-Daten verfuegbar. Als erledigt markiert, kein Retry.")
        mark_scraped(conn, turnier_id)
        return 0, 0

    total_entries = 0
    total_winners = 0
    for ev in events:
        draw = get_json(f"tournament/{tournament_code}/draw/{ev['eventCode']}")

        # WICHTIG: eventCode aus /events ist NICHT zuverlaessig mit /draw/{eventCode} verknuepft
        # (beobachtet: /events sagt eventCode=1 -> "MS U17", draw/1 liefert aber "XD U17").
        # Die Disziplin deshalb immer aus der Draw-Antwort selbst lesen, nie aus der
        # events-Liste uebernehmen. drawData kann auch als expliziter null-Wert vorkommen (nicht
        # nur als fehlender Key), z.B. bei Multi-Sport-Events wie dem European Youth Olympic
        # Festival mit abweichender Turnierstruktur -- .get(...) or {} statt Default in .get().
        draw_data = draw.get("drawData") or {}
        draw_event_label = draw_data.get("eventLabel")
        disziplin = disziplin_from_event_label(draw_event_label) if draw_event_label else None
        if disziplin is None:
            print(f"  WARNUNG: kein/unbekanntes drawData.eventLabel {draw_event_label!r} "
                  f"(eventCode={ev['eventCode']!r}), Disziplin uebersprungen")
            continue

        elim = draw.get("tournamentEliminationDrawDTO")
        cols = elim.get("eliminationDrawColumnDTOS") if elim else None
        if not cols:
            print(f"  {disziplin}: kein KO-Draw (vermutlich reines Gruppensystem) -- uebersprungen")
            continue

        cols_by_col = {c["col"]: c for c in cols}
        first_col = cols_by_col[max(cols_by_col)]

        n_entries = import_entries(conn, turnier_id, disziplin, first_col)
        n_platzierungen = import_placements(conn, turnier_id, disziplin, cols_by_col)
        print(f"  {disziplin}: {n_entries} Entries, {n_platzierungen} Platzierungen")
        total_entries += n_entries
        total_winners += n_platzierungen

    mark_scraped(conn, turnier_id)
    print(f"  -> {total_entries} Entries, {total_winners} Platzierungen gesamt")
    return total_entries, total_winners


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-resume", action="store_true", help="auch bereits verarbeitete Turniere erneut abrufen")
    ap.add_argument("--limit", type=int, default=None, help="nur die ersten N (noch offenen) Turniere verarbeiten")
    args = ap.parse_args()

    conn = sqlite3.connect(DB_PATH)
    try:
        query = "SELECT turnier_id, tournament_code, name FROM turnier"
        if not args.no_resume:
            query += " WHERE entries_scraped_at IS NULL"
        query += " ORDER BY jahr, kw"
        rows = conn.execute(query).fetchall()
        if args.limit:
            rows = rows[: args.limit]

        print(f"{len(rows)} Turniere zu verarbeiten (resume={'aus' if args.no_resume else 'an'}).")
        grand_entries = 0
        grand_winners = 0
        errors = []
        for turnier_id, code, name in rows:
            try:
                e, w = fetch_tournament(conn, turnier_id, code, name)
                grand_entries += e
                grand_winners += w
            except Exception as ex:
                print(f"  FEHLER bei {name} ({code}): {ex}")
                errors.append((name, code, str(ex)))

        print(f"\nFertig. {grand_entries} Entries, {grand_winners} Platzierungen importiert, {len(errors)} Fehler.")
        for name, code, err in errors:
            print(f"  - {name} ({code}): {err}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
