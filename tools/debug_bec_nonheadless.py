"""Testet, ob ein NICHT-headless (aber weiterhin automatisierter Selenium-)Zugriff auf
badmintoneurope.com an Cloudflare vorbeikommt -- waere die Voraussetzung fuer eine vollautomatische
Batch-Pipeline statt manueller Claude-in-Chrome-Steuerung pro Turnier."""
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from selenium.webdriver.common.by import By
from cookie_handler import setup_driver

CODE = "791F81C3-4D70-4E20-A37B-CE1EB7DB4BDE"  # anderes Turnier: 1. Living Sport Hungarian Intl 2025
url = f"https://badmintoneurope.com/web/corporate/tournament?tournament_code={CODE}&tournament_tab=matches"

driver = setup_driver(headless=False, window_size=(1400, 1000), zoom_level=100)
try:
    driver.get(url)
    time.sleep(6)
    print("title:", driver.title)
    print("current_url:", driver.current_url)
    body_text = driver.find_element(By.TAG_NAME, "body").text
    print(f"body text length: {len(body_text)}")
    print(body_text[:1500])
finally:
    driver.quit()
