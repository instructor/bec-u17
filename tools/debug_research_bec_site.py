"""Recherche: badmintoneurope.com als oeffentliche Alternative zu tournamentsoftware.com
(User-Hinweis 2026-09-18): https://badmintoneurope.com/web/corporate/tournament?tournament_code=<GUID>
React/Liferay-SPA (Komponenten TournamentDraws/TournamentMatches/TournamentEntries/TournamentHistory
im Page-Source sichtbar) -- braucht laengeres Warten auf Client-Side-Rendering."""
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from selenium.webdriver.common.by import By
from cookie_and_consent_handler import setup_driver

CODE = "E6A03CB2-5983-4BEF-BD3E-CA76F0776893"  # Spanish U17 Open 2025
url = f"https://badmintoneurope.com/web/corporate/tournament?tournament_code={CODE}"

driver = setup_driver(headless=True, window_size=(1400, 1000), zoom_level=100)
try:
    driver.get(url)
    time.sleep(3)

    # Cookie-Banner wegklicken (ACCEPT ALL), falls vorhanden
    try:
        for btn in driver.find_elements(By.TAG_NAME, "button"):
            if btn.text.strip().upper() in ("ACCEPT ALL", "ACCEPT"):
                btn.click()
                print("cookie banner accepted via button:", btn.text)
                break
    except Exception as e:
        print("cookie banner click failed:", e)

    time.sleep(5)  # React-App Zeit zum Laden/Fetchen geben

    print("title:", driver.title)
    print("current_url:", driver.current_url)

    body_text = driver.find_element(By.TAG_NAME, "body").text
    out_txt = Path(__file__).resolve().parent / "_debug_bec_body_text.txt"
    out_txt.write_text(body_text, encoding="utf-8")
    print(f"body text length: {len(body_text)} chars, saved to {out_txt}")

    out_html = Path(__file__).resolve().parent / "_debug_bec_page.html"
    out_html.write_text(driver.page_source, encoding="utf-8")
    print("saved html to", out_html)

    # Nach Tabs/Links fuer Draws/Players/Matches/Results suchen
    for a in driver.find_elements(By.TAG_NAME, "a"):
        t = a.text.strip()
        if t and any(k in t.lower() for k in ["draw", "player", "match", "result", "entr"]):
            print("LINK:", repr(t), "|", a.get_attribute("href"))
finally:
    driver.quit()
