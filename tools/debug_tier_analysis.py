import csv
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")

RESULTS_DIR = r"C:\Users\Edi Klein\OneDrive\dev-projects\bec_u17_auswertung\_RESULTS"

# 1) Gesamt-Datei: ein Wert je Turnier (avg_elo_gesamt), inkl. bec17type
with open(f"{RESULTS_DIR}\\turnier_staerke_gesamt.csv", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f, delimiter=";")
    rows = list(reader)

print(f"Spalten: {reader.fieldnames}")
print(f"Anzahl Turniere: {len(rows)}\n")

by_tier = defaultdict(list)
for r in rows:
    tier = r.get("bec17type", "?")
    val = float(r["avg_elo_gesamt"]) if r.get("avg_elo_gesamt") else None
    if val is not None:
        by_tier[tier].append((val, r.get("name"), r.get("datum")))

print("=== Ø avg_elo_gesamt je Tier ===")
for tier, vals in sorted(by_tier.items(), key=lambda kv: -sum(v[0] for v in kv[1]) / len(kv[1])):
    scores = [v[0] for v in vals]
    print(f"{tier:<10} n={len(scores):>3}  Ø={sum(scores)/len(scores):8.1f}  min={min(scores):8.1f}  max={max(scores):8.1f}")

print("\n=== Rangfolge aller Turniere nach avg_elo_gesamt (Top 15) ===")
rows_sorted = sorted(rows, key=lambda r: -float(r["avg_elo_gesamt"]) if r.get("avg_elo_gesamt") else 0)
for r in rows_sorted[:15]:
    print(f"{r['avg_elo_gesamt']:>8}  {r.get('bec17type'):<8}  {r.get('datum')}  {r.get('name')}")

print("\n=== Bottom 15 ===")
for r in rows_sorted[-15:]:
    print(f"{r['avg_elo_gesamt']:>8}  {r.get('bec17type'):<8}  {r.get('datum')}  {r.get('name')}")
