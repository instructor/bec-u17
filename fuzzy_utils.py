# fuzzy_utils.py
"""
Hilfsfunktionen für robustes Fuzzy-Matching von Namen.
Entfernt Akzente und normalisiert Unicode-Zeichen.
"""

import unicodedata
from rapidfuzz import fuzz

def normalize_name(s: str) -> str:
    """
    Normalisiert Namen für fuzzy Vergleich:
    - wandelt in lowercase um
    - entfernt Akzente (z.B. 'ž' -> 'z')
    - entfernt führende / nachgestellte Leerzeichen
    """
    if not s:
        return ""
    s = s.strip().lower()
    s = unicodedata.normalize("NFD", s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return s

def compare_names(a: str, b: str) -> float:
    """
    Vergleicht zwei Namen robust gegen diakritische Zeichen (Akzente).
    Gibt den Fuzzy-Ratio-Wert zurück (0–100).
    """
    return fuzz.ratio(normalize_name(a), normalize_name(b))
