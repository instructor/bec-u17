"""
load_from_master.py
Ersetzt fetch_bec_data.py (Matches) und fetch_bec_entries_winners.py (Entries + Platzierungen): fuellt
u17_int.db bzw. u19_int.db (BEC_AK, siehe ak_config.py) aus der Master-DB C:\\_BRAIN_MASTER_DATA statt direkt
aus der BEC-Datenhub-API (Plan Master-Data Phase 9, Schritt 5, 2026-11-23). Die Master-DB laedt dieselbe API
woechentlich (Quelle bec_api, Phase 6 abgenommen: u17_int.db 48/48 Turniere, 8.884 Matches identisch).

Schema und alle nachgelagerten Skripte (compute_rangliste, compute_elo, compute_official_strength,
export_spielerrangliste, build_site) bleiben unveraendert. Spieler-Schluessel bleibt bec_player_id (aus
match_participant.quell_id bzw. player_foreign.bec_player_id), vorhandene spieler_id bleiben damit stabil.

Je Turnier der Tabelle "turnier" (Katalog, load_turnierkatalog.py):
  matches            alle Master-Matches des Turniers mit Sieger (wie bisher matchState F: auch Walkover,
                     dann ergebnis leer), disziplin JE/ME/JD/MD/XD -> BS/GS/BD/GD/XD, bec_match_id = quell_match_id
  entries            Master-Tabelle entry (erste Draw-Runde), Reihenfolge lfd
  turnier_ergebnisse Master-Tabelle placement (platz = Beginn der Platzierungsgruppe, wie bisher)
Turniere, die die Master-DB nicht kennt oder nicht geladen hat, bleiben unveraendert (Meldung).
Nicht zuordenbare Spieler (kein bec_player_id) werden gemeldet und das Match/die Zeile ausgelassen.

Aufruf:  python load_from_master.py [--db PFAD] [--dry-run]
"""
import argparse
import datetime as dt
import sqlite3
import sys
from collections import Counter
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "_BRAIN_LIB"))
import masterdata_reader as mdr  # noqa: E402

from ak_config import DB_PATH  # noqa: E402

DIS = {"JE": "BS", "ME": "GS", "JD": "BD", "MD": "GD", "XD": "XD"}


def _geschlecht(g):
    g = (g or "").strip().upper()[:1]
    return {"M": "M", "W": "W", "F": "W"}.get(g)


class Spieler:
    """player_uid (Master) -> spieler_id (u17/u19_int.db) ueber bec_player_id."""

    def __init__(self, conn, m):
        self.conn, self.m = conn, m
        self.bec = {}  # uid -> bec_player_id
        konflikt = Counter()
        for uid, qid in m.execute("SELECT DISTINCT mp.player_uid, mp.quell_id FROM match_participant mp "
                                  "JOIN match ma ON ma.match_id = mp.match_id WHERE ma.quelle = 'bec_api'"):
            if qid and str(qid).isdigit():
                if uid in self.bec and self.bec[uid] != int(qid):
                    konflikt[uid] += 1
                self.bec.setdefault(uid, int(qid))
        for uid, bid in m.execute("SELECT player_uid, bec_player_id FROM player_foreign WHERE bec_player_id IS NOT NULL"):
            self.bec.setdefault(uid, int(bid))
        self.konflikte = konflikt
        self.vorhanden = dict(conn.execute("SELECT bec_player_id, spieler_id FROM player"))
        self.neu = 0
        self.ohne_bec = Counter()

    def id(self, uid):
        if uid is None:
            return None
        bid = self.bec.get(uid)
        if bid is None:
            self.ohne_bec[uid] += 1
            return False
        sid = self.vorhanden.get(bid)
        if sid is None:
            f = self.m.execute("SELECT nachname, vorname, land, geschlecht, bec_member_id FROM player_foreign "
                               "WHERE bec_player_id = ? LIMIT 1", (bid,)).fetchone()
            pm = self.m.execute("SELECT nachname, vorname, land, geschlecht, dbv_spieler_id FROM player_master "
                                "WHERE player_uid = ?", (uid,)).fetchone()
            q = f or pm
            sid = self.conn.execute(
                "INSERT INTO player (bec_player_id, bec_member_id, german_spieler_id, name, vorname, gender, nation) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (bid, f["bec_member_id"] if f else None, pm["dbv_spieler_id"] if pm else None,
                 q["nachname"] if q else None, q["vorname"] if q else None,
                 _geschlecht(q["geschlecht"]) if q else None, q["land"] if q else None)).lastrowid
            self.vorhanden[bid] = sid
            self.neu += 1
        return sid


def lade_turnier(conn, m, sp, turnier_id, code):
    it = m.execute("SELECT fetch_status, fetched_at FROM international_tournament WHERE upper(code) = upper(?)",
                   (code,)).fetchone()
    if it is None:
        return None
    stat = Counter()
    conn.execute("DELETE FROM matches WHERE turnier_id = ?", (turnier_id,))
    rows = m.execute("SELECT match_id, quell_match_id, disziplin, runde, datum, saetze, sieger FROM match "
                     "WHERE quelle = 'bec_api' AND upper(turnier_code) = upper(?) AND sieger IN (1, 2)", (code,))
    for r in rows.fetchall():
        dis = DIS.get(r["disziplin"])
        if dis is None:
            stat["match_disziplin_unbekannt"] += 1
            continue
        team = {1: [None, None], 2: [None, None]}
        for t, pos, uid in m.execute("SELECT team, position, player_uid FROM match_participant WHERE match_id = ? "
                                     "ORDER BY team, position", (r["match_id"],)):
            team[t][pos - 1] = sp.id(uid)
        if False in team[1] + team[2]:
            stat["match_spieler_ohne_bec_id"] += 1
            continue
        conn.execute(
            "INSERT INTO matches (bec_match_id, turnier_id, disziplin, runde, spieldatum, heim_spieler1_id, "
            "heim_spieler2_id, gast_spieler1_id, gast_spieler2_id, ergebnis, winner_seite) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (int(r["quell_match_id"]), turnier_id, dis, r["runde"], (r["datum"] or "")[:10] or None,
             *team[1], *team[2], r["saetze"] or "", "heim" if r["sieger"] == 1 else "gast"))
        stat["matches"] += 1

    for tabelle, ziel, wert in (("entry", "entries", "seed"), ("placement", "turnier_ergebnisse", "platz")):
        conn.execute(f"DELETE FROM {ziel} WHERE turnier_id = ?", (turnier_id,))
        for kon, p1, p2, w in m.execute(f"SELECT konkurrenz, player1_uid, player2_uid, {wert} FROM {tabelle} "
                                        "WHERE upper(turnier_code) = upper(?) ORDER BY konkurrenz, lfd", (code,)):
            dis = DIS.get((kon or "").split()[0])
            s1, s2 = sp.id(p1), sp.id(p2)
            if dis is None or s1 in (None, False) or s2 is False:
                stat[f"{ziel}_ausgelassen"] += 1
                continue
            spalte = "seed" if ziel == "entries" else "platzierung"
            conn.execute(f"INSERT INTO {ziel} (turnier_id, disziplin, spieler1_id, spieler2_id, {spalte}) "
                         "VALUES (?, ?, ?, ?, ?)", (turnier_id, dis, s1, s2, w))
            stat[ziel] += 1
    stempel = it["fetched_at"] or dt.datetime.now().isoformat(timespec="seconds")
    conn.execute("UPDATE turnier SET scraped_at = ?, entries_scraped_at = ? WHERE turnier_id = ?",
                 (stempel, stempel, turnier_id))
    stat["status_" + str(it["fetch_status"])] += 1
    return stat


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DB_PATH, help=f"Ziel-DB (Standard {DB_PATH} laut BEC_AK)")
    ap.add_argument("--dry-run", action="store_true", help="alles rechnen, nichts speichern")
    a = ap.parse_args()
    conn = sqlite3.connect(a.db)
    with closing(mdr.connect()) as m:
        sp = Spieler(conn, m)
        gesamt, fehlt = Counter(), []
        for tid, code, name in conn.execute("SELECT turnier_id, tournament_code, name FROM turnier ORDER BY jahr, kw").fetchall():
            st = lade_turnier(conn, m, sp, tid, code) if code else None
            if st is None:
                fehlt.append(name)
                continue
            gesamt.update(st)
        print(f"Ziel {a.db}: {dict(gesamt)}")
        print(f"neue Spieler {sp.neu}; Master-uid mit mehreren BEC-IDs {len(sp.konflikte)}; "
              f"ohne BEC-ID {len(sp.ohne_bec)} Spieler ({sum(sp.ohne_bec.values())} Bezuege)")
        if fehlt:
            print(f"{len(fehlt)} Turniere nicht in der Master-DB (unveraendert): {fehlt}")
    if a.dry_run:
        conn.rollback()
        print("dry-run: nichts gespeichert")
    else:
        conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
