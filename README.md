# BEC-U17-Auswertung

Berechnet aus den Ergebnissen des internationalen BEC-U17-Circuits eine eigene Teilnehmer- und
Turnierstärke-Rangliste. Schwesterprojekt zu `../bec_u15_auswertung`. Details, Architektur und
Phasenplan: siehe `CLAUDE.md`.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python create_db.py
.venv\Scripts\python load_turnierkatalog.py
```

## Status

Phase 0 + Phase 1 abgeschlossen: `turnier`-Tabelle mit allen 48 BEC-U17-Turnieren (2025+2026)
gefüllt. Noch keine Spieler/Matches gescraped (Phase 2).
