"""Phase 9 (Master-Data) Schritt 5: Struktur der Master-Tabellen entry/placement/match_participant neben u17_int.db,
an einem Beispielturnier (read-only). Grundlage fuer load_from_master.py."""
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT.parent / "_BRAIN_LIB"))
import masterdata_reader as mdr  # noqa: E402

alt = sqlite3.connect(f"file:{ROOT / 'u17_int.db'}?mode=ro", uri=True)
code, tid, name = alt.execute("SELECT tournament_code, turnier_id, name FROM turnier WHERE scraped_at IS NOT NULL "
                              "ORDER BY jahr DESC, kw DESC LIMIT 1").fetchone()
print("Beispiel:", name, code)
print("alt matches:", alt.execute("SELECT * FROM matches WHERE turnier_id=? LIMIT 2", (tid,)).fetchall())
print("alt player:", alt.execute("SELECT * FROM player LIMIT 2").fetchall())
print("alt entries:", alt.execute("SELECT * FROM entries WHERE turnier_id=? LIMIT 2", (tid,)).fetchall())
print("alt ergebnisse:", alt.execute("SELECT * FROM turnier_ergebnisse WHERE turnier_id=? LIMIT 3", (tid,)).fetchall())
print("alt Zaehlung:", [alt.execute(f"SELECT COUNT(*) FROM {t} WHERE turnier_id=?", (tid,)).fetchone()[0]
                        for t in ("matches", "entries", "turnier_ergebnisse")])

m = mdr.connect()
for t in ("entry", "placement", "player_foreign", "international_tournament"):
    print(t, [c[1] for c in m.execute(f"PRAGMA table_info({t})")])
print("master it:", tuple(m.execute("SELECT * FROM international_tournament WHERE upper(code)=upper(?)", (code,)).fetchone()))
mm = m.execute("SELECT * FROM match WHERE upper(turnier_code)=upper(?) LIMIT 2", (code,)).fetchall()
print("master match:", [tuple(r) for r in mm])
print("master participant:", [tuple(r) for r in m.execute("SELECT * FROM match_participant WHERE match_id=?",
                                                           (mm[0]["match_id"],))])
for t in ("entry", "placement"):
    col = [c[1] for c in m.execute(f"PRAGMA table_info({t})")]
    k = next(c for c in col if "code" in c or c == "turnier_code")
    print(f"master {t}:", [tuple(r) for r in m.execute(f"SELECT * FROM {t} WHERE upper({k})=upper(?) LIMIT 3", (code,))])
    print(f"master {t} Zaehlung:", m.execute(f"SELECT COUNT(*) FROM {t} WHERE upper({k})=upper(?)", (code,)).fetchone()[0])
print("master match Zaehlung:", m.execute("SELECT quelle, ergebnis_status, COUNT(*) FROM match WHERE upper(turnier_code)"
                                          "=upper(?) GROUP BY 1, 2", (code,)).fetchall())
print("international_tournament level/kategorie:",
      [tuple(r) for r in m.execute("SELECT level, kategorie, COUNT(*) FROM international_tournament GROUP BY 1, 2")])
