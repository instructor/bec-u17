"""Kopiert die fuer die Website benoetigten JSON-Exporte aus _RESULTS nach data/.

Die Seiten im Repo-Root (GitHub Pages, Quelle: master + / (root)) laden ihre Daten per
fetch("data/<name>.json") relativ zur HTML-Datei. Nach einem Neulauf von compute_elo.py /
export_spielerrangliste.py / compute_official_strength.py dieses Skript ausfuehren, damit die
veroeffentlichte Seite die neuen Zahlen bekommt:

    python build_site.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "_RESULTS"
DATA = ROOT / "data"

# Quelldatei in _RESULTS -> Zielname unter data/ (identisch, aber explizit gelistet, damit
# nicht versehentlich der komplette _RESULTS-Ordner veroeffentlicht wird)
FILES = [
    "turnier_staerke.json",
    "turnier_staerke_offiziell.json",
    "spielerrangliste.json",
    # U19/Junior (BEC_AK=U19, siehe ak_config.py): Quelle _RESULTS/U19/, Ziel mit Praefix u19_
    ("U19/turnier_staerke.json", "u19_turnier_staerke.json"),
]


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    pairs = [(f, f) if isinstance(f, str) else f for f in FILES]
    missing = [src for src, _ in pairs if not (RESULTS / src).is_file()]
    if missing:
        print("FEHLT in _RESULTS: " + ", ".join(missing))
        print("Erst die zugehoerigen compute_*/export_*-Skripte laufen lassen.")
        return 1

    for src_name, dst_name in pairs:
        src = RESULTS / src_name
        shutil.copy2(src, DATA / dst_name)
        print("%-34s %8.1f KB -> data/%s" % (src_name, src.stat().st_size / 1024, dst_name))

    print("Fertig. Danach committen und pushen, damit GitHub Pages neu baut.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
