"""Vergleich original u17_int.db/u19_int.db vs. Kopie nach load_from_master.py (Phase 9 Schritt 5).
Schluessel ueber BEC-IDs (spieler_id ist DB-intern). Matches: bec_match_id -> (disziplin, runde, datum, Spieler,
ergebnis, winner); entries/turnier_ergebnisse als Multimenge (Turniercode, disziplin, bec-IDs, seed/platz).
Aufruf: python tools/debug_load_from_master_vergleich.py <original.db> <kopie.db>"""
import sqlite3
import sys
from collections import Counter


def lade(p):
    c = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    bec = dict(c.execute("SELECT spieler_id, bec_player_id FROM player"))
    code = dict(c.execute("SELECT turnier_id, tournament_code FROM turnier"))
    b = lambda s: bec.get(s) if s is not None else None  # noqa: E731
    m = {r[0]: (code[r[1]], r[2], r[3], r[4], b(r[5]), b(r[6]), b(r[7]), b(r[8]), r[9] or "", r[10])
         for r in c.execute("SELECT bec_match_id, turnier_id, disziplin, runde, spieldatum, heim_spieler1_id, "
                            "heim_spieler2_id, gast_spieler1_id, gast_spieler2_id, ergebnis, winner_seite FROM matches")}
    e = Counter((code[t], d, b(s1), b(s2), sd) for t, d, s1, s2, sd in
                c.execute("SELECT turnier_id, disziplin, spieler1_id, spieler2_id, seed FROM entries"))
    te = Counter((code[t], d, b(s1), b(s2), pl) for t, d, s1, s2, pl in
                 c.execute("SELECT turnier_id, disziplin, spieler1_id, spieler2_id, platzierung FROM turnier_ergebnisse"))
    pl = {r[0]: r[1:] for r in c.execute("SELECT bec_player_id, name, vorname, gender, nation FROM player")}
    ids = dict(c.execute("SELECT bec_player_id, spieler_id FROM player"))
    return m, e, te, pl, ids


alt, neu = lade(sys.argv[1]), lade(sys.argv[2])
ma, mn = alt[0], neu[0]
nur_a, nur_n = set(ma) - set(mn), set(mn) - set(ma)
diff = [k for k in set(ma) & set(mn) if ma[k] != mn[k]]
print(f"matches: alt {len(ma)}, neu {len(mn)}, nur alt {len(nur_a)}, nur neu {len(nur_n)}, Inhalt ungleich {len(diff)}")
for k in list(nur_a)[:5]:
    print("   nur alt:", k, ma[k])
for k in list(nur_n)[:5]:
    print("   nur neu:", k, mn[k])
spalten = ["turnier", "disziplin", "runde", "datum", "h1", "h2", "g1", "g2", "ergebnis", "winner"]
feld = Counter(spalten[i] for k in diff for i in range(10) if ma[k][i] != mn[k][i])
print("   ungleiche Felder:", dict(feld))
for k in diff[:5]:
    print("   ", k, ma[k], "|", mn[k])
for name, i in (("entries", 1), ("turnier_ergebnisse", 2)):
    a, n = alt[i], neu[i]
    print(f"{name}: alt {sum(a.values())}, neu {sum(n.values())}, nur alt {sum((a - n).values())}, "
          f"nur neu {sum((n - a).values())}")
    for x in list((a - n).elements())[:4]:
        print("   nur alt:", x)
    for x in list((n - a).elements())[:4]:
        print("   nur neu:", x)
pa, pn = alt[3], neu[3]
print(f"player: alt {len(pa)}, neu {len(pn)}, neu hinzu {len(set(pn) - set(pa))}; "
      f"spieler_id geaendert: {sum(1 for k in alt[4] if neu[4].get(k) != alt[4][k])}")
