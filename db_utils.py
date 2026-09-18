"""
db_utils.py  (optimiert)
Wiederverwendbare DB-Hilfsfunktionen für player/names/matches.

Enthält:
- connect_db, safe_commit
- identify_player (mit fuzzy-Option)
- get_player_data, get_player_name
- add_name_variant
- resolve_field_conflict (generische Konfliktbehandlung, optional mit Memory-Callbacks)
- update_player_gender / update_player_nation (Wrapper, nutzt resolve_field_conflict)
"""

import sqlite3
import traceback
from typing import Optional, Tuple, List, Dict, Callable
from rapidfuzz import fuzz, process
from fuzzy_utils import compare_names  # accent-insensitive comparator
import os
import sys

def connect_db(db_path: str) -> Tuple[sqlite3.Connection, sqlite3.Cursor]:
    """Öffnet eine SQLite-DB und gibt (conn, cursor) zurück.
    Falls Datei fehlt → FileNotFoundError.
    """

    if not os.path.exists(db_path):
        raise FileNotFoundError(
            f"Datenbankdatei nicht gefunden: {db_path}"
        )

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    return conn, cursor

def safe_commit(conn: sqlite3.Connection) -> None:
    """Sicherer Commit mit Fehlertoleranz."""
    try:
        conn.commit()
    except Exception as e:
        print(f"✗ Commit-Fehler: {e}")
        traceback.print_exc()


# ---------------------
# Player / Names helpers
# ---------------------
import unicodedata

def normalize_name(s):
    """Entfernt Akzente und wandelt Unicode-Namen in vergleichbare ASCII-Form um."""
    if not s:
        return ""
    s = s.strip().lower()
    # NFD trennt Basisbuchstaben und diakritische Zeichen (z → z + ̌)
    s = unicodedata.normalize('NFD', s)
    # Entferne alle diakritischen Zeichen (Combining Marks)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    # Optional: weitere Bereinigung (z. B. Leerzeichen)
    return s


def get_player_data(spieler_id: int, cursor: sqlite3.Cursor) -> Optional[Dict]:
    """Gibt player-Zeile als Dict zurück (oder None)."""
    if not spieler_id:
        return None
    cursor.execute("""
        SELECT name, vorname, geburtsjahr, gender, club, nation
        FROM player WHERE spieler_id = ?
    """, (spieler_id,))
    row = cursor.fetchone()
    if not row:
        return None
    return {
        "name": row[0],
        "vorname": row[1],
        "geburtsjahr": row[2],
        "gender": row[3],
        "club": row[4],
        "nation": row[5]
    }


def get_player_name(spieler_id: int, cursor: sqlite3.Cursor) -> str:
    """Gibt formatierten Namen zurück oder 'Spieler <id>'."""
    pdata = get_player_data(spieler_id, cursor)
    if pdata:
        return f"{pdata.get('vorname') or ''} {pdata.get('name') or ''}".strip()
    return f"Spieler {spieler_id}"


def get_player_id(name: str, vorname: str, cursor: sqlite3.Cursor) -> int:
    """
    Sucht den Spieler (name, vorname) in der DB-Tabelle "names".
    Gibt spieler_id zurück, falls gefunden, sonst 0.
    Vergleich erfolgt case- und akzent-insensitiv via normalize_name().
    """
    if not name or not vorname:
        return 0

    # Normalisierte Eingaben
    n_name = normalize_name(name)
    n_vorname = normalize_name(vorname)

    # 1) Exakte Suche (case-sensitive in DB, aber nach normalisierten Strings)
    cursor.execute("""
        SELECT DISTINCT spieler_id, name, vorname FROM names
    """)
    all_rows = cursor.fetchall()
    if not all_rows:
        return 0

    # Schritt 1: Exakte Übereinstimmung (nach Normalisierung)
    for pid, db_name, db_vorname in all_rows:
        if (normalize_name(db_name) == n_name and
            normalize_name(db_vorname) == n_vorname):
            return pid
    return 0

'''
    # Schritt 2: Falls kein exakter Treffer, versuche umgekehrte Reihenfolge (Zhang Nina vs Nina Zhang)
    for pid, db_name, db_vorname in all_rows:
        if normalize_name(db_name) == n_vorname and normalize_name(db_vorname) == n_name:
            return pid

    # Schritt 3: Fuzzy-Annäherung mit compare_names
    best_pid = 0
    best_score = 0
    for pid, db_name, db_vorname in all_rows:
        full_score = compare_names(f"{vorname} {name}", f"{db_vorname} {db_name}")
        if full_score > best_score:
            best_score = full_score
            best_pid = pid

    if best_score >= 90:
        print(f"✅ get_player_id(): Automatischer Treffer für '{vorname} {name}' → ID {best_pid} (Score {best_score:.1f})")
        return best_pid
    elif best_score >= 70:
        print(f"⚠ get_player_id(): Unsicherer Treffer für '{vorname} {name}' → ID {best_pid} (Score {best_score:.1f})")
'''


def add_name_variant(conn: sqlite3.Connection, cursor: sqlite3.Cursor, spieler_id: int, name: str, vorname: str) -> None:
    """Fügt eine Namensvariante in names ein, falls noch nicht vorhanden."""
    cursor.execute(
        "SELECT 1 FROM names WHERE spieler_id = ? AND name = ? AND vorname = ?",
        (spieler_id, name, vorname)
    )
    if cursor.fetchone() is None:
        cursor.execute(
            "INSERT INTO names (spieler_id, name, vorname) VALUES (?, ?, ?)",
            (spieler_id, name, vorname)
        )
        safe_commit(conn)
        print(f"  ➕ Neue Namensvariante: {vorname} {name}")


# ---------------------
# Fuzzy / Identify
# ---------------------
def _load_all_names_list(cursor: sqlite3.Cursor) -> List[Tuple[int, str, str]]:
    """Hilfsfunktion: Liefert Liste von (spieler_id, name, vorname) aus DB (distinct)."""
    cursor.execute("""
        SELECT DISTINCT n.spieler_id, n.name, n.vorname
        FROM names n
        JOIN player p ON n.spieler_id = p.spieler_id
    """)
    return cursor.fetchall()


# Neue, verbesserte identify_player:
def identify_player(search_string: str, cursor, auto_threshold: int = 90, suggest_threshold: int = 70, use_cache: dict = None) -> int:
    """
    Identifiziert einen Spieler anhand eines Suchstrings (z.B. "Nina Zhang" oder "Zhang Nina").
    Strategie:
      1) Exakte Suche in player (alle Teile müssen irgendwo matchen)
      2) Fallback: Exakte Suche in names (alternative Schreibweisen)
      3) Fuzzy über alle vorhandenen Namens-Labels (vorname name), vergleich via compare_names()
         - Auto-Assign bei score >= auto_threshold
         - Vorschläge (Liste) bei score >= suggest_threshold (interaktiv)
    Args:
        search_string: Eingabestring (CSV, etc.)
        cursor: DB-Cursor
        auto_threshold: Schwelle für automatische Zuordnung (default 90)
        suggest_threshold: Schwelle, ab der Vorschläge angezeigt werden (default 70)
        use_cache: optional dict mit Key "all_names" um mehrfaches Laden zu vermeiden

    Returns:
        spieler_id (int) oder 0 wenn nicht gefunden / Abbruch
    """
    import re
    if not search_string or not search_string.strip():
        return 0

    # clean input (remove [] sections etc.)
    s = re.sub(r'\[.*?\]', '', search_string).strip()
    parts = [p.strip() for p in s.split() if p.strip()]
    if len(parts) == 0:
        return 0

    # 1) Exakte Suche in player (alle Teile müssen matchen)
    query = "SELECT spieler_id FROM player WHERE 1=1"
    params = []
    for part in parts:
        query += " AND (name = ? OR vorname = ?)"
        params.extend([part, part])
    cursor.execute(query, params)
    rows = cursor.fetchall()
    if len(rows) == 1:
        return rows[0][0]
    # if multiple exact matches, continue to fuzzy disambiguation below

    # 2) Exakte Suche in names (alternative Schreibweisen)
    query = "SELECT DISTINCT spieler_id FROM names WHERE 1=1"
    params = []
    for part in parts:
        query += " AND (name = ? OR vorname = ?)"
        params.extend([part, part])
    cursor.execute(query, params)
    rows = cursor.fetchall()
    if len(rows) == 1:
        return rows[0][0]
    # else continue to fuzzy

    # 3) Fuzzy search across all names (use cache if provided)
    if use_cache and use_cache.get("all_names"):
        all_names = use_cache["all_names"]
    else:
        cursor.execute("SELECT DISTINCT n.spieler_id, n.name, n.vorname FROM names n JOIN player p ON n.spieler_id = p.spieler_id")
        all_names = cursor.fetchall()  # list of tuples (spieler_id, name, vorname)
        if use_cache is not None:
            use_cache["all_names"] = all_names

    if not all_names:
        return 0

    # Build labels "Vorname Name" (and optionally "Name Vorname" — token_sort handles order)
    labels = [f"{r[2]} {r[1]}" for r in all_names]

    # Use rapidfuzz.process.extract but with our compare_names as scorer:
    # rapidfuzz.process.extract requires a scorer from rapidfuzz; we emulate by computing scores manually.
    scored = []
    for idx, (pid, name, vorname) in enumerate(all_names):
        # compute two comparisons and average:
        score_full = compare_names(s, f"{vorname} {name}")  # compare search to "vorname name"
        # Also compare component-wise and average to give robustness
        first_part = parts[0] if len(parts) >= 1 else ""
        last_part = parts[-1] if len(parts) >= 1 else ""
        score_vorname = compare_names(first_part, vorname) if first_part else 0
        score_name = compare_names(last_part, name) if last_part else 0
        combined = (score_full * 0.6) + (score_vorname * 0.2) + (score_name * 0.2)
        scored.append((pid, name, vorname, combined))

    # sort by combined score desc
    scored.sort(key=lambda x: x[3], reverse=True)

    best_pid, best_name, best_vorname, best_score = scored[0]

    # Auto-assign if strong match
    if best_score >= auto_threshold:
        print(f"✅ Automatischer Treffer: '{search_string}' => {best_vorname} {best_name} (ID {best_pid}) (Score {best_score:.1f})")
        return best_pid

    # Build suggestions list for interactive disambiguation
    suggestions = [(pid, name, vorname, sc) for pid, name, vorname, sc in scored if sc >= suggest_threshold]
    if suggestions:
        print(f"⚠ Kein eindeutiger Treffer für '{search_string}'. Vorschläge (Score):")
        for i, (pid, name, vorname, sc) in enumerate(suggestions[:8], start=1):
            print(f"  {i}: {vorname} {name} (ID {pid}) - {sc:.1f}")
        choice = input("Wähle Nummer oder Enter zum Abbrechen: ").strip()
        if choice.isdigit():
            ci = int(choice) - 1
            if 0 <= ci < len(suggestions[:8]):
                chosen = suggestions[ci]
                return chosen[0]

    # nothing found
    print(f"⚠ Keine sinnvollen Vorschläge für '{search_string}' (best: {best_vorname} {best_name} [{best_score:.1f}])")
    return 0



'''
def identify_player(search_string: str, cursor: sqlite3.Cursor,
                    auto_threshold: int = 90, suggest_threshold: int = 70) -> int:
    """
    Identifiziert einen Spieler anhand eines Suchstrings (z.B. "Nina Zhang").
    Strategie:
      1) Exakte Suche in player (alle Teile als name/vorname)
      2) Exakte Suche in names
      3) Fuzzy über alle Namen (token_sort_ratio), automatische Zuweisung bei >= auto_threshold
      4) Bei Vorschlägen (>= suggest_threshold) interaktive Auswahl

    Returns:
        spieler_id (int) oder 0, wenn nicht gefunden/abgebrochen
    """
    if not search_string or not search_string.strip():
        return 0

    import re
    s = re.sub(r'\[.*?\]', '', search_string).strip()
    parts = s.split()
    if len(parts) < 1:
        return 0

    # 1) Exakte Suche in player (alle Teile müssen irgendwo matchen)
    query = "SELECT spieler_id FROM player WHERE 1=1"
    params = []
    for part in parts:
        query += " AND (name = ? OR vorname = ?)"
        params.extend([part, part])
    cursor.execute(query, params)
    rows = cursor.fetchall()
    if len(rows) == 1:
        return rows[0][0]

    # 2) Exakte Suche in names
    query = "SELECT DISTINCT spieler_id FROM names WHERE 1=1"
    params = []
    for part in parts:
        query += " AND (name = ? OR vorname = ?)"
        params.extend([part, part])
    cursor.execute(query, params)
    rows = cursor.fetchall()
    if len(rows) == 1:
        return rows[0][0]

    # 3) Fuzzy
    all_names = _load_all_names_list(cursor)  # list of (id, name, vorname)
    if not all_names:
        return 0

    # Build list of "Vorname Name"
    all_labels = [f"{r[2]} {r[1]}" for r in all_names]
    # Use token_sort_ratio for robustness against ordering
    results = process.extract(s, all_labels, scorer=fuzz.token_sort_ratio, limit=8)

    # results: list of tuples (label, score, idx)
    if not results:
        return 0

    best_label, best_score, best_idx = results[0]
    if best_score >= auto_threshold:
        matched = all_names[best_idx]
        print(f"✅ Automatischer Treffer: '{best_label}' (Score {best_score}) -> ID {matched[0]}")
        return matched[0]

    # Show suggestions above threshold
    suggestions = [(lbl, sc, idx) for lbl, sc, idx in results if sc >= suggest_threshold]
    if suggestions:
        print(f"⚠ Kein eindeutiger Treffer für '{search_string}'. Vorschläge:")
        for i, (lbl, sc, idx) in enumerate(suggestions, 1):
            print(f"  {i}: {lbl} (Score {sc})")
        choice = input("Wähle Nummer oder Enter zum Abbrechen: ").strip()
        if choice.isdigit():
            ci = int(choice) - 1
            if 0 <= ci < len(suggestions):
                _, _, idx = suggestions[ci]
                matched = all_names[idx]
                # return spieler_id
                return matched[0]
    else:
        print(f"⚠ Keine sinnvollen Vorschläge für '{search_string}' (best: {best_label} [{best_score}]).")

    return 0
'''

# ---------------------
# Konfliktauflösung (generisch)
# ---------------------
ChoiceRecallFn = Optional[Callable[[str, dict, list], Optional[int]]]  # (prompt, context, options) -> index or None
ChoiceRememberFn = Optional[Callable[[str, dict, dict], None]]      # (prompt, context, chosen_option) -> None


def resolve_field_conflict(prompt: str, db_value: str, csv_value: str,
                           recall_fn: ChoiceRecallFn = None,
                           remember_fn: ChoiceRememberFn = None) -> str:
    """
    Generische Konfliktauflösung für ein Feld (z. B. Nation oder Club).

    - recall_fn(prompt, context, options) sollte optional eine gespeicherte Index-Antwort zurückgeben.
    - remember_fn(prompt, context, chosen_option) speichert die Entscheidung.

    Rückgabe: der gewählte Wert (db_value oder csv_value)
    """
    # Normiertes Kontextobjekt
    context = {
        "field_values": {"db": db_value, "csv": csv_value}
    }
    options = [
        {"idx": 1, "label": f"DB: {db_value}", "value": db_value},
        {"idx": 2, "label": f"CSV: {csv_value}", "value": csv_value}
    ]

    # Versuch Recall (falls vorhanden)
    if recall_fn:
        try:
            idx = recall_fn(prompt, context, options)
            if isinstance(idx, int):
                chosen = options[idx]["value"] if idx < len(options) else (db_value if idx == 1 else csv_value)
                # Note: recall_decision in memory_manager returns 0..n; we expect 1..n here
                # We'll map accordingly in callers. For safety, handle common cases:
                if idx == 0:  # some memories return 0 for 'new' semantics; ignore
                    pass
                else:
                    # convert idx (0-based) to index into options (1..)
                    try:
                        return options[idx - 1]["value"]
                    except Exception:
                        return db_value
        except Exception:
            pass

    # Fallback: ask user
    print(f"  ⚠ Konflikt: {prompt}  → DB='{db_value}'  CSV='{csv_value}'")
    choice = input("    Welche Quelle verwenden? [1=DB, 2=CSV] (Enter=DB): ").strip()
    choice_index = 1 if choice == "" else (int(choice) if choice.isdigit() and choice in ["1", "2"] else 1)
    chosen_value = db_value if choice_index == 1 else csv_value

    # Remember if possible
    if remember_fn:
        try:
            remember_fn(prompt, context, {"choice_index": choice_index, "chosen": chosen_value})
        except Exception:
            pass

    return chosen_value


def update_player_gender(cursor: sqlite3.Cursor, conn: sqlite3.Connection,
                         spieler_id: int, expected_gender: str) -> None:
    """Setzt Gender, falls leer; bei Widerspruch nur ausgeben (keine automatische Änderung)."""
    if not spieler_id:
        return
    cursor.execute("SELECT gender FROM player WHERE spieler_id = ?", (spieler_id,))
    row = cursor.fetchone()
    if not row:
        return
    current = row[0]
    if current is None or str(current).strip() == "":
        cursor.execute("UPDATE player SET gender = ? WHERE spieler_id = ?", (expected_gender, spieler_id))
        safe_commit(conn)
        print(f"  ✓ Gender für {get_player_name(spieler_id, cursor)} gesetzt: {expected_gender}")
    elif str(current).strip() != expected_gender:
        print(f"  ⚠ Gender-Konflikt für {get_player_name(spieler_id, cursor)}: DB='{current}', erwartet='{expected_gender}'")
        # keine automatische Änderung - interaktiv Entscheidung optional


def update_player_nation(cursor: sqlite3.Cursor, conn: sqlite3.Connection,
                         spieler_id: int, csv_nation: str,
                         recall_fn: ChoiceRecallFn = None,
                         remember_fn: ChoiceRememberFn = None) -> None:
    """
    Aktualisiert Nation nach Regeln:
      - falls DB leer -> CSV übernehmen
      - falls unterschiedlich -> resolve_field_conflict (optional Memory callbacks)
    """
    if not spieler_id or not csv_nation or not str(csv_nation).strip():
        return

    cursor.execute("SELECT nation FROM player WHERE spieler_id = ?", (spieler_id,))
    row = cursor.fetchone()
    if row is None:
        return
    db_nation = (row[0] or "").strip()
    if not db_nation:
        cursor.execute("UPDATE player SET nation = ? WHERE spieler_id = ?", (csv_nation, spieler_id))
        safe_commit(conn)
        print(f"  ✓ Nation für {get_player_name(spieler_id, cursor)} ergänzt: {csv_nation}")
    elif db_nation != csv_nation:
        prompt = f"Nation-Konflikt für Spieler {spieler_id}"
        chosen = resolve_field_conflict(prompt, db_nation, csv_nation, recall_fn=recall_fn, remember_fn=remember_fn)
        if chosen != db_nation:
            cursor.execute("UPDATE player SET nation = ? WHERE spieler_id = ?", (chosen, spieler_id))
            safe_commit(conn)
            print(f"  ✓ Nation für {get_player_name(spieler_id, cursor)} auf '{chosen}' aktualisiert.")
