import re
import unicodedata

# ---------- Hilfsfunktionen ----------

seed_re = re.compile(r'\s*\[[^\]]+\]')  # entfernt [2], [3/4], etc.

def remove_seed(s: str) -> str:
    """Entfernt Setzplatzinfos in eckigen Klammern und trimmt."""
    if not s:
        return ""
    return seed_re.sub("", s).strip()

def normalize_str(s: str) -> str:
    """
    Normalisiert Namen für Vergleiche:
     - entfernt Seeds,
     - Unicode-Normalisierung (diakritika entfernen),
     - Kleinschreibung,
     - entfernt Punkt/Komma am Ende, mehrere Leerzeichen -> 1,
     - lässt Bindestrich und Apostroph (aber vereinheitlicht typographische Varianten).
    """
    if not s:
        return ""
    s = remove_seed(s)
    # typographische Apostrophe vereinheitlichen
    s = s.replace("’", "'").replace("‘", "'").replace("`", "'")
    # Unicode-Normalisierung und Entfernen diakritischer Zeichen
    s_nfkd = unicodedata.normalize("NFKD", s)
    s_ascii = "".join(ch for ch in s_nfkd if not unicodedata.combining(ch))
    s_ascii = s_ascii.lower()
    # Entferne führende/trailing punctuation (Punkt, Komma)
    s_ascii = re.sub(r'^[\s\.,;:-]+|[\s\.,;:-]+$', '', s_ascii)
    # Mehrere Leerzeichen zu einem
    s_ascii = re.sub(r'\s+', ' ', s_ascii).strip()
    return s_ascii

def tokens_of(s: str):
    """Gibt tokens einer normalisierten Zeichenkette zurück (Worte, behält Bindestriche/')."""
    ns = normalize_str(s)
    if not ns:
        return []
    # Split by space only — hyphens and apostrophes kept in tokens
    return ns.split(' ')

# ---------- Player-Index aufbauen (für schnellen Lookup) ----------

def build_player_index(players):
    """
    Erwartet players: Liste von dicts mit 'name' (Nachname), 'vorname' (Vorname).
    Liefert:
      - set_exact: Set von (norm_name, norm_vorname)
      - players_list: Liste der originalen Einträge mit normalisierten Token-Listen für Fallback-Matching
    """
    set_exact = set()
    players_list = []
    for p in players:
        name = p.get("name", "") or ""
        vorname = p.get("vorname", "") or ""
        norm_name = normalize_str(name)
        norm_vor = normalize_str(vorname)
        set_exact.add((norm_name, norm_vor))
        players_list.append({
            "orig": p,
            "norm_name": norm_name,
            "norm_vor": norm_vor,
            "name_tokens": tokens_of(name),
            "vor_tokens": tokens_of(vorname)
        })
    return set_exact, players_list

# ---------- Verbesserte split- und matching-Funktionen ----------

def split_match_name(fullname: str, players, max_parts=4):
    """
    Teilt einen Match-Namen im Format "Vorname1 Vorname2 ... Nachname1 Nachname2 ..."
    in (nachname, vorname). Versucht mehrere Splits und vergleicht mit players.
    - fullname: string aus der Match-Ansicht (vorname(s) + nachname(s))
    - players: Liste wie in deiner Pipeline (player dicts)
    Rückgabe: (nachname, vorname) — beide als ursprüngliche Reihenfolge (nicht normalisiert).
    Wenn kein Match gefunden wird, Fallback: letzte "Wortgruppe" als Nachname.
    """
    if not fullname:
        return "", ""

    # Vorbereitung
    raw = remove_seed(fullname).strip()
    words = raw.split()
    n_words = len(words)

    # Direkter Heuristik-Fallback (wenn sehr kurz)
    if n_words == 1:
        return words[0], ""

    # Baue Index für Lookup
    set_exact, players_list = build_player_index(players)

    # Versuche alle sinnvollen Splits:
    # Wir erlauben bis max_parts words für Vorname und bis max_parts für Nachname,
    # also splits bei position i: 1..n_words-1, wobei len(first)<=max_parts and len(last)<=max_parts
    for i in range(1, n_words):  # i = Anzahl Wörter im VORNAMEN
        vor_words = words[:i]
        name_words = words[i:]
        if len(vor_words) > max_parts or len(name_words) > max_parts:
            continue
        vor_candidate = " ".join(vor_words)
        name_candidate = " ".join(name_words)

        # Normalisiere und prüfe exaktes Matching
        norm_v = normalize_str(vor_candidate)
        norm_n = normalize_str(name_candidate)
        if (norm_n, norm_v) in set_exact:
            # Treffer — gib in originaler Reihenfolge zurück (Nachname, Vorname)
            return name_candidate, vor_candidate

    # Kein exakter Treffer — fallback auf token-overlap Fallback:
    # Erstelle norm tokens für fullname
    for i in range(1, n_words):
        vor_words = words[:i]
        name_words = words[i:]
        if len(vor_words) > max_parts or len(name_words) > max_parts:
            continue
        vor_candidate = " ".join(vor_words)
        name_candidate = " ".join(name_words)
        cand_v_tokens = tokens_of(vor_candidate)
        cand_n_tokens = tokens_of(name_candidate)

        # Durchsuche alle players nach hohem Token-Overlap
        for p in players_list:
            # match wenn alle cand_n_tokens in p.name_tokens UND alle cand_v_tokens in p.vor_tokens
            if cand_n_tokens and cand_v_tokens:
                if all(t in p["name_tokens"] for t in cand_n_tokens) and all(t in p["vor_tokens"] for t in cand_v_tokens):
                    # Rückgabe in Original-Form (wie im Match gefunden)
                    return name_candidate, vor_candidate

    # Wenn noch kein Treffer: heuristischer Standard: letztes Wort = Nachname
    # aber wir unterstützen Mehrwort-Nachnamen: versuche bis max_parts Varianten, bevorzuge längere Nachnamen
    for k in range(1, min(max_parts, n_words-1) + 1):
        name_candidate = " ".join(words[-k:])
        vor_candidate = " ".join(words[:-k])
        # Normalisiere und prüfe lose Match (Teil-Übereinstimmung)
        norm_n = normalize_str(name_candidate)
        norm_v = normalize_str(vor_candidate)
        for p in players_list:
            if norm_n and norm_n in p["norm_name"]:
                # Found partial surname match
                return name_candidate, vor_candidate

    # Endgültiger Fallback
    return words[-1], " ".join(words[:-1])

def player_in_list(vorname: str, nachname: str, players) -> bool:
    """
    Robustere Implementierung:
     - nutzt normalize_str und build_player_index (fast lookup)
     - falls kein exakter norm match -> Token-overlap Fallback (sicher, tolerant)
    """
    if not (vorname or nachname):
        return False

    norm_v = normalize_str(vorname)
    norm_n = normalize_str(nachname)

    set_exact, players_list = build_player_index(players)
    if (norm_n, norm_v) in set_exact:
        return True

    # Fallback: Token-Overlap (alle tokens des Kandidaten sollten im jeweiligen Feld des Players erscheinen)
    v_tokens = tokens_of(vorname)
    n_tokens = tokens_of(nachname)
    if not (v_tokens or n_tokens):
        return False

    for p in players_list:
        # Wenn Kandidatenvorname-Tokens alle in player vorname tokens UND Kandidatennachname-Tokens alle in player name tokens
        ok_v = all(t in p["vor_tokens"] for t in v_tokens) if v_tokens else True
        ok_n = all(t in p["name_tokens"] for t in n_tokens) if n_tokens else True
        if ok_v and ok_n:
            return True

    return False
