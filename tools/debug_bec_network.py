"""Recherche: welche JSON-API ruft die badmintoneurope.com React-App fuer Turnierdaten auf?
Erfasst Netzwerk-Requests via Chrome-Performance-Log (CDP), um die tatsaechliche Datenquelle
hinter der TournamentDraws/TournamentMatches/TournamentEntries-Komponenten zu finden."""
import json
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

CODE = "E6A03CB2-5983-4BEF-BD3E-CA76F0776893"  # Spanish U17 Open 2025
url = f"https://badmintoneurope.com/web/corporate/tournament?tournament_code={CODE}"

options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

driver = webdriver.Chrome(options=options)
try:
    driver.get(url)
    time.sleep(8)  # React-App + XHR-Fetches Zeit geben

    logs = driver.get_log("performance")
    print(f"{len(logs)} performance log entries")

    urls_seen = set()
    for entry in logs:
        try:
            msg = json.loads(entry["message"])["message"]
        except Exception:
            continue
        if msg.get("method") == "Network.requestWillBeSent":
            req_url = msg["params"]["request"]["url"]
            if req_url not in urls_seen:
                urls_seen.add(req_url)
                print("REQ:", req_url)

finally:
    driver.quit()
