"""Einmalige Recherche (Phase 2): reale Draw-Link-Beschriftungen eines BEC-U17-Turniers ansehen,
um die Disziplin-Pattern in draw_scraper.py fuer BD/GD/XD korrekt zu erweitern."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cookie_and_consent_handler import setup_driver, accept_cookies_and_consent
from selenium.webdriver.common.by import By

CODE = "E6A03CB2-5983-4BEF-BD3E-CA76F0776893"  # Spanish U17 Open 2025
main_url = f"https://www.tournamentsoftware.com/tournament/{CODE}"
draws_url = f"https://www.tournamentsoftware.com/sport/draws.aspx?id={CODE}"

driver = setup_driver(headless=True, window_size=(1200, 900), zoom_level=100)
try:
    driver.get(main_url)
    accept_cookies_and_consent(driver, use_tracking=True)
    print("main page title:", driver.title)
    print("main current_url:", driver.current_url)

    driver.get(draws_url)
    accept_cookies_and_consent(driver, use_tracking=True)
    time.sleep(2)
    print("draws page title:", driver.title)
    print("draws current_url:", driver.current_url)
    links = driver.find_elements(By.CSS_SELECTOR, "table.ruler a[href*='draw']")
    print(f"found {len(links)} draw links (table.ruler)")
    all_a_with_draw = driver.find_elements(By.CSS_SELECTOR, "a[href*='draw']")
    print(f"found {len(all_a_with_draw)} <a href*=draw> anywhere on page")
    for l in all_a_with_draw[:30]:
        print(repr(l.text.strip()), "|", l.get_attribute("href"))

    out = Path(__file__).resolve().parent / "_debug_draws_page.html"
    out.write_text(driver.page_source, encoding="utf-8")
    print("saved page source to", out)
finally:
    driver.quit()
