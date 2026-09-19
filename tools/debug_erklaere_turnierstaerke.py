"""Zeigt an EINEM konkreten Turnier/Disziplin nachvollziehbar, wie die Turnierstaerke entsteht:
die Vor-Turnier-Elo aller Teilnehmer, die daraus ausgewaehlten Top 16 und deren Mittelwert.
Reine Erklaer-/Verifikationshilfe, aendert nichts. Aufruf:

    python tools/debug_erklaere_turnierstaerke.py [DISZIPLIN] [TURNIER-NAMENSFRAGMENT]
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from compute_elo import (  # noqa: E402
    TOP_N_STRENGTH,
    compute_elo_for_disziplin,
    load_matches,
)

DISZIPLIN = sys.argv[1] if len(sys.argv) > 1 else "BS"
NAME_FRAGMENT = sys.argv[2] if len(sys.argv) > 2 else "Spanish"

conn = sqlite3.connect("u17_int.db")
matches = load_matches(conn, DISZIPLIN)
ratings, match_counts, pre = compute_elo_for_disziplin(matches)

row = conn.execute(
    "SELECT turnier_id, name, jahr, bec17type FROM turnier WHERE name LIKE ? LIMIT 1",
    ("%" + NAME_FRAGMENT + "%",),
).fetchone()
if row is None:
    raise SystemExit("Kein Turnier mit '%s' im Namen gefunden." % NAME_FRAGMENT)
turnier_id, tname, tjahr, ttier = row

teilnehmer = sorted(
    {p for (tid, p) in pre if tid == turnier_id},
    key=lambda p: pre[(turnier_id, p)],
    reverse=True,
)
namen = {
    r[0]: "%s %s (%s)" % (r[1], r[2], r[3])
    for r in conn.execute("SELECT spieler_id, vorname, name, nation FROM player")
}

print("Turnier : %s (%s, Tier %s), Disziplin %s" % (tname, tjahr, ttier, DISZIPLIN))
print("Spieler mit mindestens einem Match hier: %d" % len(teilnehmer))
print()
print("Rang  Vor-Turnier-Elo  Spieler")
for i, p in enumerate(teilnehmer, 1):
    marker = " <- geht in die Top-%d ein" % TOP_N_STRENGTH if i <= TOP_N_STRENGTH else ""
    print("%4d  %15.1f  %s%s" % (i, pre[(turnier_id, p)], namen.get(p, p), marker))
    if i == TOP_N_STRENGTH + 3:
        print("      ... (%d weitere, gehen NICHT in die Staerke ein)" % (len(teilnehmer) - i))
        break

top = [pre[(turnier_id, p)] for p in teilnehmer[:TOP_N_STRENGTH]]
print()
print("Summe der Top %d      : %.1f" % (len(top), sum(top)))
print("Turnierstaerke (Ø)   : %.1f" % (sum(top) / len(top)))
voll = [pre[(turnier_id, p)] for p in teilnehmer]
print("(Vergleich Volltfeld-Ø: %.1f -- so wurde es bis 2026-09-19 gerechnet)" % (sum(voll) / len(voll)))
conn.close()
