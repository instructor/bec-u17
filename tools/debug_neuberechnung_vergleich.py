"""Neuberechnung 2026-11-24 (Datenquelle Master-DB): Turnierstaerke-JSONs alt (git HEAD) vs. neu.
Erwartung: Elo-Turnierstaerke der bisherigen Turniere unveraendert (Rating-Stand VOR dem Turnier, spaetere
Turniere wirken nicht zurueck); neue Turniere kommen hinzu; offizielle Staerke aendert sich nur bei EYOF 2025
(Entries neu). Aufruf: python tools/debug_neuberechnung_vergleich.py <datei unter data/>"""
import json
import subprocess
import sys

datei = sys.argv[1]
alt = json.loads(subprocess.run(["git", "show", f"HEAD:data/{datei}"], capture_output=True).stdout.decode("utf-8"))
neu = json.load(open(f"data/{datei}", encoding="utf-8"))


def zeilen(d):
    out = {}
    for teil in ("gesamt", "je_disziplin"):
        x = d.get(teil)
        items = x.items() if isinstance(x, dict) else [("", x)]
        for dis, rows in items:
            for r in rows or []:
                key = (teil, dis, r.get("turnier_id") or r.get("name"))
                out[key] = {k: v for k, v in r.items() if k not in ("rang",)}
    return out


a, n = zeilen(alt), zeilen(neu)
gleich = sum(1 for k in a if k in n and a[k] == n[k])
anders = [k for k in a if k in n and a[k] != n[k]]
print(f"{datei}: alt {len(a)}, neu {len(n)} Zeilen; gleich {gleich}, geaendert {len(anders)}, "
      f"weg {len(set(a) - set(n))}, neu hinzu {len(set(n) - set(a))}")
for k in anders[:6]:
    diff = {f: (a[k].get(f), n[k].get(f)) for f in set(a[k]) | set(n[k]) if a[k].get(f) != n[k].get(f)}
    print("   geaendert", k, diff)
namen = sorted({n[k].get("name") for k in set(n) - set(a) if k[0] == "gesamt"})
print("   neue Turniere (gesamt):", namen)
