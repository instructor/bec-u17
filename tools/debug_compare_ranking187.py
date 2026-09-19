import csv
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

import os

RESULTS_DIR = r"C:\Users\Edi Klein\OneDrive\dev-projects\bec_u17_auswertung\_RESULTS"
HTML_PATH = os.environ.get("RANKING_HTML", r"C:\Users\EDIKLE~1\AppData\Local\Temp\save_body.html")

DISZIPLIN_MAP = {
    "Men's singles": "BS",
    "Women's singles": "GS",
    "Men's doubles": "BD",
    "Women's doubles": "GD",
    "Mixed doubles": "XD",
}


def parse_official(html_path):
    with open(html_path, encoding="utf-8") as f:
        html = f.read()
    rows = re.findall(r"<tr.*?</tr>", html, re.S)
    official = {code: [] for code in DISZIPLIN_MAP.values()}
    current = None
    for r in rows:
        header_match = re.search(r'category=\d+">([^<]+)</a>', r)
        if header_match and header_match.group(1).strip() in DISZIPLIN_MAP:
            current = DISZIPLIN_MAP[header_match.group(1).strip()]
            continue
        rank_match = re.search(r'<td class="rank"><div[^>]*>(\d+)</div></td>', r)
        if not rank_match or not current:
            continue
        rank = int(rank_match.group(1))
        name_match = re.search(r'player\.aspx[^"]*"[^>]*>([^<]+)</a>', r)
        name = name_match.group(1).strip() if name_match else "?"
        nation_match = re.search(r"\[([A-Z]{3})\]", r)
        nation = nation_match.group(1) if nation_match else "?"
        tail_nums = re.findall(r"<td[^>]*>(\d+)</td>", r)
        member_id = tail_nums[-2] if len(tail_nums) >= 2 else "?"
        points = tail_nums[-1] if tail_nums else "?"
        official[current].append((rank, name, nation, member_id, points))
    return official


def load_our_ranking(disziplin):
    path = f"{RESULTS_DIR}\\rangliste_{disziplin}.csv"
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            rows.append(row)
    return rows


def load_elo_ranking(disziplin):
    path = f"{RESULTS_DIR}\\elo_spieler.csv"
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            if row["disziplin"] == disziplin:
                rows.append(row)
    rows.sort(key=lambda r: -float(r["elo"]))
    return rows


def find_name(rows, official_name):
    # official name format: "FIRSTNAME LASTNAME" (lastname often uppercase)
    parts = official_name.split()
    lastname_guess = parts[-1].upper()
    for i, row in enumerate(rows, start=1):
        if row["name"].upper() == lastname_guess:
            return i, row
    # try matching bec_player_id later if needed
    return None, None


official = parse_official(HTML_PATH)

for disziplin in ["BS", "GS", "BD", "GD", "XD"]:
    our_rows = load_our_ranking(disziplin)
    total = len(our_rows)
    print(f"\n=== {disziplin} (total unsere Rangliste: {total} Zeilen) ===")
    elo_rows = load_elo_ranking(disziplin)
    print(f"{'Off.Rang':>8} {'Name':<28} {'Nation':<6} {'Off.Pkt':>7}  | {'Pkt-Rang':>8} | {'Elo-Rang':>8} {'Elo':>7}")
    pkt_percentiles = []
    elo_percentiles = []
    for rank, name, nation, member_id, points in official[disziplin]:
        our_rank, our_row = find_name(our_rows, name)
        elo_rank, elo_row = find_name(elo_rows, name)
        pkt_str = str(our_rank) if our_row else "?"
        elo_str = f"{elo_rank}" if elo_row else "?"
        elo_val = elo_row["elo"] if elo_row else "?"
        print(f"{rank:>8} {name:<28} {nation:<6} {points:>7}  | {pkt_str:>8} | {elo_str:>8} {elo_val:>7}")
        if our_row:
            pkt_percentiles.append(100 * our_rank / total)
        if elo_row:
            elo_percentiles.append(100 * elo_rank / len(elo_rows))
    if pkt_percentiles:
        print(f"  -> Punkte-Rangliste: Top-{max(pkt_percentiles):.1f}% (Median {sorted(pkt_percentiles)[len(pkt_percentiles)//2]:.1f}%) aller {total} Spieler")
    if elo_percentiles:
        print(f"  -> Elo-Rangliste:    Top-{max(elo_percentiles):.1f}% (Median {sorted(elo_percentiles)[len(elo_percentiles)//2]:.1f}%) aller {len(elo_rows)} Spieler")
