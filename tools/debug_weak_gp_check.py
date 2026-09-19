"""Prueft, ob die schwachen GP-Turniere (MALOW Polish 2025/2026, VICTOR JOT 2026) echtes Signal
oder ein Datenproblem sind: wie viele Matches/Teilnehmer liegen vor, und wie sehen die Top-16
Vor-Turnier-Ratings aus, die tatsaechlich in den Schnitt eingeflossen sind?"""
import sqlite3
import sys
from collections import defaultdict

sys.path.insert(0, ".")
from compute_elo import DISZIPLINEN, load_matches, compute_elo_for_disziplin, TOP_N_STRENGTH

TURNIER_IDS = {26: "MALOW Polish 2025", 34: "MALOW Polish 2026", 33: "VICTOR JOT 2026", 9: "Austrian Int. 2025 (Referenz, Rang 1)"}

conn = sqlite3.connect("u17_int.db")

for disziplin in DISZIPLINEN:
    matches = load_matches(conn, disziplin)
    ratings, match_counts, pre_tournament = compute_elo_for_disziplin(matches)

    participants_by_turnier = defaultdict(set)
    for m in matches:
        for pid in (m["heim"][0], m["heim"][1], m["gast"][0], m["gast"][1]):
            if pid is not None:
                participants_by_turnier[m["turnier_id"]].add(pid)

    for tid, label in TURNIER_IDS.items():
        if tid not in participants_by_turnier:
            continue
        werte = [pre_tournament[(tid, p)] for p in participants_by_turnier[tid] if (tid, p) in pre_tournament]
        werte.sort(reverse=True)
        top = werte[:TOP_N_STRENGTH]
        if not top:
            continue
        print(f"{disziplin} | {label:<32} n_teilnehmer={len(werte):>3}  top16_n={len(top):>2}  "
              f"top16_avg={sum(top)/len(top):7.1f}  top1={top[0]:7.1f}  top16={top[-1]:7.1f}")
