"""Phase 9 Schritt 5: welche BEC-Turniere (level u17 bzw. junior/major_championships) kennt die Master-DB, die im
Katalog (turnier-Tabelle) von u17_int.db / u19_int.db fehlen? Mit Kategorie, Status, Matchzahl. Read-only."""
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT.parent / "_BRAIN_LIB"))
import masterdata_reader as mdr  # noqa: E402

m = mdr.connect()
for db, levels in (("u17_int.db", ("u17",)), ("u19_int.db", ("junior", "major_championships"))):
    katalog = {c.upper() for (c,) in sqlite3.connect(ROOT / db).execute("SELECT tournament_code FROM turnier") if c}
    rows = m.execute(f"SELECT code, name, level, kategorie, jahr, kw, fetch_status, n_matches FROM international_tournament "
                     f"WHERE level IN ({','.join('?' * len(levels))}) ORDER BY jahr, kw", levels).fetchall()
    neu = [r for r in rows if r["code"].upper() not in katalog]
    print(f"\n{db}: Master {len(rows)} Turniere ({'/'.join(levels)}), Katalog {len(katalog)}, nicht im Katalog {len(neu)}")
    for r in neu:
        print(f"   {r['jahr']} KW{r['kw']:02d}  {str(r['kategorie']):<10} {r['fetch_status']:<12} "
              f"{r['n_matches'] or 0:>4}  {r['name']}")
# U17-Konkurrenzen auch in Turnieren anderer level (z.B. EM U17 als major_championships)?
print("\nTurniere mit U17-Konkurrenzen nach level:",
      [tuple(r) for r in m.execute("SELECT it.level, COUNT(DISTINCT it.code) FROM match ma JOIN international_tournament it "
                                    "ON it.code = ma.turnier_code WHERE ma.konkurrenz LIKE '% U17' GROUP BY 1")])
