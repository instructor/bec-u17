"""
fetch_official_ranking.py
Laedt die offizielle "BEC U17 Circuit Ranking" (tournamentsoftware.com, rid=187) komplett (alle
Seiten je Disziplin, nicht nur die Top-10 der Uebersichtsseite) und speichert sie als
_RESULTS/offizielle_rangliste_{disziplin}.csv.

Hintergrund: paralleler, von unserer eigenen Elo-Berechnung UNABHAENGIGER Ansatz fuer die
Turnierstaerke (User-Wunsch 2026-09-19) -- statt Spielstaerke aus unseren eigenen Matchdaten
abzuleiten, wird hier die offizielle BEC-Punktzahl jedes Spielers als externes Staerkemass
verwendet: ein Turnier ist stark, wenn viele hoch platzierte Spieler laut offizieller Rangliste
teilgenommen haben (siehe compute_official_strength.py).

Join-Schluessel: die "Member ID" der offiziellen Rangliste entspricht exakt unserer
player.bec_member_id (Verbands-Mitgliedsnummer, stabil) -- verifiziert an mehreren Spielern
(z.B. Andre LOOSKARI EST: 34123 in beiden Quellen identisch). Kein Fuzzy-Name-Matching noetig.

Cookiewall: die Seite verlangt ohne Cookie-Consent-Cookie einen Redirect auf /cookiewall/; wird
hier per einfachem POST auf /cookiewall/Save einmalig aufgeloest (kein Browser noetig, siehe
Session-Recherche 2026-09-19).
"""
import csv
import os
import re
import time

import requests

BASE = "https://www.tournamentsoftware.com"
RID = 187
CATEGORY_IDS = {"BS": 2354, "GS": 2355, "BD": 2356, "GD": 2357, "XD": 2358}
OUT_DIR = "_RESULTS"
REQUEST_DELAY_SECONDS = 0.3
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; bec-u17-auswertung/1.0)"}


def make_session():
    s = requests.Session()
    s.headers.update(HEADERS)
    r = s.get(f"{BASE}/cookiewall/", params={"returnurl": f"/ranking/ranking.aspx?rid={RID}"})
    r.raise_for_status()
    s.post(
        f"{BASE}/cookiewall/Save",
        data={
            "CookiePurposes": ["1", "2", "4", "16"],
            "ReturnUrl": f"/ranking/ranking.aspx?rid={RID}",
            "SelectedLCID": "",
            "SettingsOpen": "False",
        },
    )
    return s


def latest_week_id(session):
    r = session.get(f"{BASE}/ranking/ranking.aspx", params={"rid": RID})
    r.raise_for_status()
    m = re.search(r'<option selected="selected" value="(\d+)"', r.text)
    if not m:
        raise RuntimeError("Konnte aktuelle Ranking-Woche nicht ermitteln")
    return int(m.group(1))


def parse_category_page(html):
    rows = re.findall(r"<tr.*?</tr>", html, re.S)
    out = []
    for r in rows:
        rank_match = re.search(r'<td class="rank"><div[^>]*>(\d+)</div></td>', r)
        if not rank_match:
            continue
        name_match = re.search(r'player\.aspx[^"]*"[^>]*>([^<]+)</a>', r)
        nation_match = re.search(r"\[([A-Z]{3})\]", r)
        tail_nums = re.findall(r"<td[^>]*>(\d+)</td>", r)
        if not name_match or len(tail_nums) < 2:
            continue
        out.append(
            {
                "rang": int(rank_match.group(1)),
                "name": name_match.group(1).strip(),
                "nation": nation_match.group(1) if nation_match else "",
                "member_id": tail_nums[-2],
                "punkte": int(tail_nums[-1]),
            }
        )
    return out


def fetch_category(session, week_id, category_id):
    all_rows = []
    page = 1
    while True:
        r = session.get(
            f"{BASE}/ranking/category.aspx",
            params={"id": week_id, "category": category_id, "p": page, "ps": 100},
        )
        r.raise_for_status()
        rows = parse_category_page(r.text)
        if not rows:
            break
        all_rows.extend(rows)
        if len(rows) < 100:
            break
        page += 1
        time.sleep(REQUEST_DELAY_SECONDS)
    return all_rows


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    session = make_session()
    week_id = latest_week_id(session)
    print(f"Ranking-Woche (aktuellste): id={week_id}")

    for disziplin, category_id in CATEGORY_IDS.items():
        rows = fetch_category(session, week_id, category_id)
        path = os.path.join(OUT_DIR, f"offizielle_rangliste_{disziplin}.csv")
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["rang", "name", "nation", "member_id", "punkte"], delimiter=";")
            writer.writeheader()
            writer.writerows(rows)
        print(f"{disziplin}: {len(rows)} Spieler -> {path}")
        time.sleep(REQUEST_DELAY_SECONDS)


if __name__ == "__main__":
    main()
