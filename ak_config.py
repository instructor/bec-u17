"""
ak_config.py
Altersklassen-Umschaltung fuer die gesamte Pipeline (User-Wunsch 2026-09-26: Turnierstaerke-
Auswertung analog U17 auch fuer U19/Junior). Gewaehlt ueber die Umgebungsvariable BEC_AK
(Default "U17" -- alle bisherigen Aufrufe/Pfade fuer U17 bleiben unveraendert):

    BEC_AK=U19 python fetch_bec_data.py        (bash)
    $env:BEC_AK="U19"; python fetch_bec_data.py (PowerShell)

U19 bekommt eine eigene DB und eigene Ergebnisdateien; das Schema ist identisch. Die Spalte
turnier.bec17type traegt bei U19 den Junior-Turniertyp ("U19 JIS"/"U19 JIC"/"U19 JIGP"/
"U19 EJC"/"U19 WJC"/"U19 JFS") -- Spaltenname aus U17 uebernommen, damit alle Skripte und die
Web-Seiten ohne Umbenennung funktionieren.
"""
import os

AK = os.environ.get("BEC_AK", "U17").upper()

_CONFIG = {
    "U17": {
        "db_path": "u17_int.db",
        "catalog_dir": os.path.join("_TOURNAMENT_DATA", "BEC-U17-Circuit"),
        "type_column": "BEC17type",
        "out_dir": "_RESULTS",
        "web_prefix": "",
    },
    "U19": {
        "db_path": "u19_int.db",
        "catalog_dir": os.path.join("_TOURNAMENT_DATA", "BEC-U19-Junior"),
        "type_column": "BEC19type",
        "out_dir": os.path.join("_RESULTS", "U19"),
        "web_prefix": "u19_",
    },
}
if AK not in _CONFIG:
    raise SystemExit(f"Unbekannte Altersklasse BEC_AK={AK!r}, erlaubt: {', '.join(_CONFIG)}")

DB_PATH = _CONFIG[AK]["db_path"]
CATALOG_DIR = _CONFIG[AK]["catalog_dir"]
TYPE_COLUMN = _CONFIG[AK]["type_column"]
OUT_DIR = _CONFIG[AK]["out_dir"]
WEB_PREFIX = _CONFIG[AK]["web_prefix"]  # Praefix der JSON-Dateien unter data/ fuer die Website
os.makedirs(OUT_DIR, exist_ok=True)
