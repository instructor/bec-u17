"""Prueft fuer mehrere BEC-U17-Turniere, ob die tournamentsoftware.com-Hauptseite frei zugaenglich
ist oder auf eine bwf.tournamentsoftware.com-Login-Seite umleitet."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sqlite3
from cookie_and_consent_handler import setup_driver, accept_cookies_and_consent

conn = sqlite3.connect(str(Path(__file__).resolve().parent.parent / "u17_int.db"))
cur = conn.cursor()
cur.execute("SELECT name, tournament_code, url FROM turnier ORDER BY turnier_id")
rows = cur.fetchall()

driver = setup_driver(headless=True, window_size=(1200, 900), zoom_level=100)
try:
    for name, code, url in rows:
        driver.get(url)
        accept_cookies_and_consent(driver, use_tracking=True)
        final = driver.current_url
        redirected = "login" in final.lower()
        print(f"{'LOGIN-REDIRECT' if redirected else 'OK':15s} {name!r:55s} -> {final}")
finally:
    driver.quit()
