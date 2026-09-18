"""
memory_manager.py
Version: 2.3 (strukturierter Vergleich, Dict-basiert)
Autor: Edi Klein / GPT-5
Datum: 2025-10-17

Zweck:
--------
Zentrale, robuste Gedächtnisverwaltung für wiederkehrende Entscheidungen
(z. B. beim Import von Spielern oder Matches in die DB).

Alle Entscheidungen werden als strukturierte Dicts gespeichert.
"""

import os
import json
import shutil
from datetime import datetime
from pathlib import Path

# =============================================================================
# --- Globale Konfiguration ---------------------------------------------------
# =============================================================================

AUX_DIR = "_AUXILIARY_DATA"
AUTO_DECISION_MODE = True  # True = automatisch anwenden, False = nur vorschlagen
MEMORY_FILE = "memory.json"

# =============================================================================
# --- Basisfunktionen ---------------------------------------------------------
# =============================================================================

def ensure_aux_dir():
    """Stellt sicher, dass das _AUXILIARY_DATA-Verzeichnis existiert."""
    os.makedirs(AUX_DIR, exist_ok=True)

def memory_path():
    """Pfad zur aktuellen Memory-Datei."""
    return os.path.join(AUX_DIR, MEMORY_FILE)

def load_memory():
    """Lädt den gespeicherten Memory-Inhalt als Dict."""
    ensure_aux_dir()
    path = memory_path()
    if Path(path).exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"⚠ Fehlerhafte {path} – wird neu angelegt.")
            return {}
    return {}

def save_memory(memory):
    """Speichert das Memory-Dict als JSON."""
    ensure_aux_dir()
    with open(memory_path(), "w", encoding="utf-8") as f:
        json.dump(memory, f, indent=2, ensure_ascii=False)

# =============================================================================
# --- Hilfsfunktionen für strukturierten Vergleich ----------------------------
# =============================================================================

def options_equal(opts1, opts2):
    """
    Vergleicht zwei Optionslisten (unabhängig von der Reihenfolge).
    Optionen sind Dicts mit vorname, name, nation, club.
    """
    def simplify(opt):
        return (
            str(opt.get("vorname", "")).strip().lower(),
            str(opt.get("name", "")).strip().lower(),
            str(opt.get("nation", "")).strip().lower(),
            str(opt.get("club", "")).strip().lower()
        )

    set1 = {simplify(o) for o in opts1 or []}
    set2 = {simplify(o) for o in opts2 or []}
    return set1 == set2

def contexts_equivalent(ctx1, ctx2):
    """
    Vergleicht zwei Entscheidungskontexte strukturiert:
    - gleicher CSV-Spieler (vorname, name, nation, club)
    - gleiche Optionsliste (unabhängig von Reihenfolge)
    """
    p1, p2 = ctx1.get("csv_player", {}), ctx2.get("csv_player", {})

    def norm(x): return str(x or "").strip().lower()
    if not all([
        norm(p1.get("vorname")) == norm(p2.get("vorname")),
        norm(p1.get("name")) == norm(p2.get("name")),
        norm(p1.get("nation")) == norm(p2.get("nation")),
        norm(p1.get("club")) == norm(p2.get("club"))
    ]):
        return False

    return options_equal(ctx1.get("options", []), ctx2.get("options", []))

# =============================================================================
# --- Hauptfunktionen für Entscheidungs-Memory -------------------------------
# =============================================================================

def remember_decision(prompt, context, chosen_option):
    """
    Speichert eine Entscheidung dauerhaft.

    prompt: text, z. B. "Matchwahl für Liam Assalit"
    context: dict mit csv_player + options
    chosen_option: dict mit {'new_player': True, ...} oder einer match-option
    """
    memory = load_memory()
    entry = {
        "prompt": prompt.strip(),
        "context": context,
        "choice_repr": chosen_option,
        "timestamp": datetime.now().isoformat(timespec="seconds")
    }
    memory[prompt.strip()] = entry
    save_memory(memory)

def recall_decision(prompt, context, current_options):
    """
    Sucht, ob eine frühere Entscheidung zum gleichen prompt existiert
    (gleicher Spieler + gleiche Optionen).

    Gibt zurück:
      - 0 für neuen Spieler
      - 1..n für die gewählte Option
      - None falls keine passende Erinnerung
    """
    memory = load_memory()
    remembered_entry = None

    # Suche Eintrag mit gleichem Prompt + Kontext
    for key, entry in memory.items():
        if entry.get("prompt") == prompt.strip():
            if contexts_equivalent(entry.get("context", {}), context):
                remembered_entry = entry
                break

    if not remembered_entry:
        return None

    choice_repr = remembered_entry.get("choice_repr")
    if not choice_repr:
        return None

    # Neuer Spieler
    if choice_repr.get("new_player"):
        if AUTO_DECISION_MODE:
            return 0
        print(f"  🧠 Erinnerung: Neuer Spieler ({choice_repr.get('vorname')} {choice_repr.get('name')})")
        return 0

    # Konfliktlösung (choice_index)
    if choice_repr.get("choice_index"):
        if AUTO_DECISION_MODE:
            return choice_repr["choice_index"]
        print(f"  🧠 Erinnerung: Konfliktentscheidung = {choice_repr['choice_index']}")
        return choice_repr["choice_index"]

    # Match-Option
    for idx, opt in enumerate(current_options, start=1):
        if options_equal([opt], [choice_repr]):
            if AUTO_DECISION_MODE:
                return idx
            print(f"  🧠 Erinnerung: Wahl = {opt.get('vorname')} {opt.get('name')} ({opt.get('score')}%)")
            return idx

    # keine passende Option
    print("  🔄 Erinnerung gefunden, aber keine passende Option – ignoriert.")
    return None

def finalize_memory_for_tournament(abbreviation, module_tag="players"):
    """
    Archiviert memory.json nach erfolgreichem Durchlauf.

    Dateiname:
        memory-<module_tag>_<abbreviation>.json
    """
    try:
        ensure_aux_dir()
        src = memory_path()
        if not Path(src).exists():
            return
        dst = os.path.join(AUX_DIR, f"memory-{module_tag}_{abbreviation}.json")
        if Path(dst).exists():
            ts = datetime.now().strftime("%Y%m%dT%H%M%S")
            dst = os.path.join(AUX_DIR, f"memory-{module_tag}_{abbreviation}_{ts}.json")
        shutil.move(src, dst)
        print(f"🧩 Memory gespeichert als: {dst}")
    except Exception as e:
        print(f"⚠ Fehler beim Archivieren der Memory-Datei: {e}")
