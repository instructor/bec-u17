"""Warum fehlen Adria U17 2025 und Liepaja Beach U17 2025 im 2025er Katalog? Grading in der Katalog-Excel, in
BRAINs 2025er Liste und in allen Master-Snapshots 2025 (wann kam 'BEC U17 Circuit')."""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT.parent / "_BRAIN_LIB"))
import masterdata_reader as mdr  # noqa: E402

MUSTER = "Adria U17|Liepaja"
kat = pd.read_excel(ROOT / "_TOURNAMENT_DATA/BEC-U17-Circuit/U19_RankingTournaments_2025_ausschliesslich-BEC-U17-Differenzierung.xlsx")
print("Katalog-Excel:", kat[kat.RankingTournamentName.str.contains(MUSTER, na=False)][["RankingTournamentName", "Grading"]].values.tolist())
brain = ROOT.parent / "_BRAIN_Badminton-RAnking-INsights/ALL_TOURNAMENTS+RESULT-RANKINGS"
for f in sorted(brain.glob("U19_RankingTournaments_2025*.xlsx")):
    d = pd.read_excel(f)
    print(f.name, d[d.RankingTournamentName.str.contains(MUSTER, na=False)][["RankingTournamentName", "Grading"]].values.tolist())
snap = sorted((mdr.base_dir() / "ALL_TOURNAMENTS+RESULT-RANKINGS").rglob("U19_RankingTournaments_2025*"))
for f in snap:
    d = pd.read_excel(f) if f.suffix == ".xlsx" else pd.read_csv(f, sep=None, engine="python", encoding="latin-1")
    print("Master", f.name, d[d.RankingTournamentName.astype(str).str.contains(MUSTER, na=False)][["Grading"]].values.ravel().tolist())
