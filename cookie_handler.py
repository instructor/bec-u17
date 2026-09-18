"""
Cookie Wall und Consent Dialog Handler für tournamentsoftware.com

Dieses Modul behandelt Cookie-Dialoge auf tournamentsoftware.com und verwandten Domains.
Es unterstützt mehrsprachige Cookie-Walls und Consent-Dialoge, die in iFrames eingebettet sein können.

Features:
- Multi-Domain Cookie-Tracking (vermeidet doppelte Behandlung)
- Mehrsprachige Cookie-Wall Unterstützung (EN, DE, NL)
- Consent-Dialog in Haupt-Dokument oder iFrames
- Robustes Exception-Handling bei Session-Problemen
- Konfigurierbares Browser-Setup (Fenstergröße, Zoom, Headless-Mode)

Hauptfunktionen:
- setup_driver(): Initialisiert Chrome WebDriver mit Optionen
- accept_cookies_and_consent(): Behandelt Cookie-Wall + Consent-Dialog
- handle_cookie_wall(): Klickt auf "Accept" Button der Cookie-Wall
- handle_consent_dialog(): Behandelt Privacy Consent Dialog (auch in iFrames)
- reset_cookie_tracker(): Setzt Domain-Tracking zurück

Verwendung:
    from cookie_handler import setup_driver, accept_cookies_and_consent

    driver = setup_driver(headless=False, window_size=(1920, 1080), zoom_level=100)
    driver.get("https://www.tournamentsoftware.com/tournament/...")
    accept_cookies_and_consent(driver)
    # ... weitere Operationen
    driver.quit()

Bekannte Einschränkungen:
- Limitiert auf max. 5 iFrames bei Consent-Dialog Suche (vermeidet Session-Crashes)
- Timeout von 2-3 Sekunden pro Selektor (Performance-Optimierung)

Version: 2.0
Datum: 2025-01-11
Autor: Edi Klein / Claude
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time


# Globaler Tracker für behandelte Domains
_cookies_accepted_for_domains = set()


def get_domain_from_url(url):
    """Extrahiert Domain aus URL"""
    import re
    match = re.search(r'https?://([^/]+)', url)
    return match.group(1) if match else None


def setup_driver(headless=False, window_size=(1920, 1080), zoom_level=100):
    """
    Richtet den Chrome WebDriver ein

    Args:
        headless: Wenn True, läuft Browser im Hintergrund
        window_size: Tuple (width, height) für Fenstergröße, z.B. (1920, 1080)
        zoom_level: Zoom-Level in Prozent (50-200), Standard ist 100

    Returns:
        WebDriver Instanz
    """
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument('--headless')
        options.add_argument(f'--window-size={window_size[0]},{window_size[1]}')

    # Force Device Scale Factor für konsistenten Zoom
    options.add_argument(f'--force-device-scale-factor={zoom_level/100}')

    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(10)

    # Fenstergröße setzen (auch im nicht-headless Modus)
    if not headless:
        driver.set_window_size(window_size[0], window_size[1])

    # Zoom über JavaScript setzen (zusätzlich zur device scale)
    try:
        zoom_percentage = zoom_level / 100
        driver.execute_script(f"document.body.style.zoom='{zoom_percentage}'")
    except:
        pass  # Falls die Seite noch nicht geladen ist

    # Cookie-Tracker zurücksetzen bei neuem Driver
    reset_cookie_tracker()

    return driver


def handle_cookie_wall(driver, timeout=15):
    """
    Behandelt die Cookie Wall von tournamentsoftware.com

    Args:
        driver: Selenium WebDriver Instanz
        timeout: Maximale Wartezeit in Sekunden

    Returns:
        True wenn erfolgreich, False bei Fehler
    """
    try:
        # Warte auf Cookie Wall und klicke ACCEPT Button
        accept_button_selectors = [
            "button.btn.btn--success.js-accept-basic",  # Aus dem HTML
            "//button[contains(@class, 'js-accept-basic')]",  # XPath Alternative
            "//button//span[contains(text(), 'Accept')]/..",  # Text-basiert
            "//button//span[contains(text(), 'ACCEPT')]/..",
            "//button//span[contains(text(), 'AKKOORD')]/.."  # Niederländisch
        ]

        button_clicked = False
        for selector in accept_button_selectors:
            try:
                if selector.startswith("//"):
                    # XPath
                    wait = WebDriverWait(driver, timeout)
                    button = wait.until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                else:
                    # CSS Selector
                    wait = WebDriverWait(driver, timeout)
                    button = wait.until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )

                button.click()
                print("✓ Cookie Wall: ACCEPT Button geklickt")
                button_clicked = True
                time.sleep(1)  # Kurze Pause nach dem Klick
                break

            except (TimeoutException, NoSuchElementException):
                continue

        if not button_clicked:
            print("⚠ Cookie Wall Button nicht gefunden (evtl. bereits akzeptiert)")
            return True  # Möglicherweise Cookies bereits gesetzt

        return True

    except Exception as e:
        print(f"✗ Fehler bei Cookie Wall: {e}")
        return False


def handle_consent_dialog(driver, timeout=15, max_iframes=5):
    """
    Behandelt den Privacy Consent Dialog (der in einem iFrame sein kann)

    Args:
        driver: Selenium WebDriver Instanz
        timeout: Maximale Wartezeit in Sekunden

    Returns:
        True wenn erfolgreich, False bei Fehler
    """
    try:
        # WICHTIG: Der Dialog kann in einem iFrame sein!
        # Warte kurz, damit der Dialog erscheint
        time.sleep(1)

        # Selektoren für den Button (DIV, kein BUTTON!)
        consent_button_selectors = [
            "div.btn.green",
            "//div[contains(@class, 'btn') and contains(@class, 'green')]",
            "//div[contains(text(), 'Accept and continue')]",
            "//div[contains(text(), 'Ich akzeptiere')]",
        ]

        button_clicked = False

        # Versuch 1: Im Haupt-Dokument
        print("   Suche Consent Dialog im Haupt-Dokument...")
        for selector in consent_button_selectors:
            try:
                if selector.startswith("//"):
                    button = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                else:
                    button = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )

                driver.execute_script("arguments[0].scrollIntoView(true);", button)
                time.sleep(0.5)
                button.click()
                print("✓ Consent Dialog: Button im Haupt-Dokument geklickt")
                button_clicked = True
                time.sleep(2)
                break
            except (TimeoutException, NoSuchElementException):
                continue

        # Versuch 2: In iFrames suchen
        if not button_clicked:
            print("   Suche Consent Dialog in iFrames...")
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            print(f"   Gefundene iFrames: {len(iframes)}")

            # Limitiere auf max_iframes um Session-Probleme zu vermeiden
            iframes_to_check = iframes[:max_iframes]
            if len(iframes) > max_iframes:
                print(f"   ℹ Limitiere auf erste {max_iframes} iFrames (von {len(iframes)})")

            for idx, iframe in enumerate(iframes_to_check):
                try:
                    driver.switch_to.frame(iframe)

                    # Versuche Button im iFrame zu finden
                    for selector in consent_button_selectors:
                        try:
                            if selector.startswith("//"):
                                button = driver.find_element(By.XPATH, selector)
                            else:
                                button = driver.find_element(By.CSS_SELECTOR, selector)

                            if button and button.is_displayed():
                                driver.execute_script("arguments[0].scrollIntoView(true);", button)
                                time.sleep(0.5)
                                button.click()
                                print(f"✓ Consent Dialog: Button in iFrame {idx} geklickt")
                                button_clicked = True
                                driver.switch_to.default_content()

                                # Warte bis der Dialog wirklich verschwunden ist
                                print("   Warte auf Schließen des Dialogs...")
                                time.sleep(3)

                                # Prüfe ob Dialog noch sichtbar ist
                                try:
                                    WebDriverWait(driver, 10).until_not(
                                        EC.presence_of_element_located((By.CSS_SELECTOR, "div[id*='consent']"))
                                    )
                                    print("   Dialog vollständig geschlossen")
                                except:
                                    pass  # Dialog ist weg oder Check fehlgeschlagen

                                break
                        except (NoSuchElementException, Exception):
                            continue

                    if button_clicked:
                        break

                    # Zurück zum Haupt-Dokument
                    driver.switch_to.default_content()

                except Exception as e:
                    # Bei Cross-Origin iFrames zurück zum Haupt-Dokument
                    driver.switch_to.default_content()
                    continue

        if not button_clicked:
            print("⚠ Consent Dialog Button nicht gefunden (weder im Haupt-Dokument noch in iFrames)")
            return False

        return True

    except Exception as e:
        print(f"✗ Fehler bei Consent Dialog: {e}")
        return False


def accept_cookies_and_consent(driver, reload_after=False):
    """
    Führt beide Schritte aus: Cookie Wall + Consent Dialog
    Trackt bereits behandelte Domains um unnötige Wiederholungen zu vermeiden

    Args:
        driver: Selenium WebDriver Instanz
        reload_after: Wenn True, lädt Seite nach Cookie-Handling neu (vermeidet Session-Probleme)

    Returns:
        True wenn beide erfolgreich, False sonst
    """
    # Aktuelle Domain prüfen
    current_url = driver.current_url
    domain = get_domain_from_url(current_url)

    # Prüfe ob für diese Domain bereits Cookies akzeptiert wurden
    if domain and domain in _cookies_accepted_for_domains:
        print(f"   ℹ Cookies für {domain} bereits akzeptiert, überspringe...")
        return True

    print(f"   → Behandle Cookies für Domain: {domain}")

    # Schritt 1: Cookie Wall
    if not handle_cookie_wall(driver):
        # Wenn Cookie Wall nicht gefunden, ist sie evtl. schon weg
        print("   ℹ Cookie Wall nicht gefunden (evtl. bereits akzeptiert)")

    # Schritt 2: Consent Dialog
    consent_result = handle_consent_dialog(driver)
    if not consent_result:
        # Wenn Consent Dialog nicht gefunden, ist er evtl. schon weg
        print("   ℹ Consent Dialog nicht gefunden (evtl. bereits akzeptiert)")

    # Domain als behandelt markieren
    if domain:
        _cookies_accepted_for_domains.add(domain)
        print(f"   ✓ Domain {domain} als behandelt markiert")

    # Optional: Seite neu laden um Session zu stabilisieren
    if reload_after and consent_result:
        print("   → Lade Seite neu um Session zu stabilisieren...")
        try:
            driver.refresh()
            time.sleep(2)
            print("   ✓ Seite neu geladen")
        except Exception as e:
            print(f"   ⚠ Fehler beim Neuladen: {e}")

    print("✓ Cookie-Handling abgeschlossen")
    return True


def reset_cookie_tracker():
    """
    Setzt den Cookie-Tracker zurück
    Nützlich wenn ein neuer Browser gestartet wird
    """
    global _cookies_accepted_for_domains
    _cookies_accepted_for_domains.clear()
    print("   Cookie-Tracker zurückgesetzt")