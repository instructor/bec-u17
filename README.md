# BEC-U17-Auswertung

Berechnet aus den Ergebnissen des internationalen BEC-U17-Circuits eine eigene Teilnehmer- und
Turnierstärke-Rangliste. Schwesterprojekt zu `../bec_u15_auswertung`. Details, Architektur und
Phasenplan: siehe `CLAUDE.md`.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python create_db.py
```

## Status

Phase 0 (Projekt-Setup) abgeschlossen. Noch keine Turnierdaten geladen/gescraped.
