"""
Cookie-Wall und Consent-Dialog Handler für tournamentsoftware.com
Wiederverwendbares Modul für Web-Scraping mit Selenium
Mit Multi-Domain Cookie-Tracking zur Vermeidung doppelter Behandlung
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import time
import json
import os
from pathlib import Path


class CookieTracker:
    """
    Verwaltet den Status von Cookie-Wall und Consent-Dialogen über mehrere Domains
    """

    def __init__(self, storage_file=None):
        """
        Initialisiert den Cookie-Tracker

        Args:
            storage_file (str): Pfad zur JSON-Datei für persistente Speicherung
                               Default: .cookie_tracker.json im aktuellen Verzeichnis
        """
        if storage_file is None:
            storage_file = Path.cwd() / '.cookie_tracker.json'

        self.storage_file = Path(storage_file)
        self.tracking_data = self._load_tracking_data()

    def _load_tracking_data(self):
        """Lädt Tracking-Daten aus Datei"""
        if self.storage_file.exists():
            try:
                with open(self.storage_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠ Fehler beim Laden der Tracking-Daten: {e}")
                return {}
        return {}

    def _save_tracking_data(self):
        """Speichert Tracking-Daten in Datei"""
        try:
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(self.tracking_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠ Fehler beim Speichern der Tracking-Daten: {e}")

    def _get_domain(self, url):
        """Extrahiert Domain aus URL"""
        parsed = urlparse(url)
        return parsed.netloc or parsed.path

    def is_handled(self, url, dialog_type='both'):
        """
        Prüft, ob Cookie-Wall/Consent bereits behandelt wurde

        Args:
            url (str): URL der Webseite
            dialog_type (str): 'cookiewall', 'consent' oder 'both'

        Returns:
            bool: True wenn bereits behandelt
        """
        domain = self._get_domain(url)

        if domain not in self.tracking_data:
            return False

        data = self.tracking_data[domain]

        if dialog_type == 'both':
            return data.get('cookiewall_handled', False) and data.get('consent_handled', False)
        elif dialog_type == 'cookiewall':
            return data.get('cookiewall_handled', False)
        elif dialog_type == 'consent':
            return data.get('consent_handled', False)

        return False

    def mark_handled(self, url, cookiewall=False, consent=False):
        """
        Markiert Domain als behandelt

        Args:
            url (str): URL der Webseite
            cookiewall (bool): Cookie-Wall wurde behandelt
            consent (bool): Consent-Dialog wurde behandelt
        """
        domain = self._get_domain(url)

        if domain not in self.tracking_data:
            self.tracking_data[domain] = {
                'cookiewall_handled': False,
                'consent_handled': False,
                'last_access': None
            }

        if cookiewall:
            self.tracking_data[domain]['cookiewall_handled'] = True
        if consent:
            self.tracking_data[domain]['consent_handled'] = True

        self.tracking_data[domain]['last_access'] = time.strftime('%Y-%m-%d %H:%M:%S')

        self._save_tracking_data()

    def reset_domain(self, url):
        """Setzt Tracking-Status für eine Domain zurück"""
        domain = self._get_domain(url)
        if domain in self.tracking_data:
            del self.tracking_data[domain]
            self._save_tracking_data()
            print(f"✓ Tracking-Status für {domain} zurückgesetzt")

    def reset_all(self):
        """Setzt alle Tracking-Daten zurück"""
        self.tracking_data = {}
        self._save_tracking_data()
        print("✓ Alle Tracking-Daten zurückgesetzt")

    def get_status(self, url=None):
        """
        Gibt Tracking-Status aus

        Args:
            url (str): Optional - URL einer bestimmten Domain

        Returns:
            dict: Tracking-Status
        """
        if url:
            domain = self._get_domain(url)
            return self.tracking_data.get(domain, None)
        return self.tracking_data


# Globale Tracker-Instanz
_global_tracker = None


def get_tracker(storage_file=None):
    """
    Gibt die globale Tracker-Instanz zurück (Singleton-Pattern)

    Args:
        storage_file (str): Optional - Pfad zur Storage-Datei

    Returns:
        CookieTracker: Tracker-Instanz
    """
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = CookieTracker(storage_file)
    return _global_tracker


def setup_driver(headless=True, window_size=(1920, 1080), zoom_level=100):
    """
    Initialisiert und konfiguriert einen Chrome WebDriver

    Args:
        headless (bool): True für Headless-Modus, False für sichtbaren Browser
        window_size (tuple): Fenstergröße als (breite, höhe) in Pixeln
        zoom_level (int): Zoom-Level in Prozent (z.B. 85 für 85%)

    Returns:
        webdriver.Chrome: Konfigurierter Chrome WebDriver

    Example:
        driver = setup_driver(headless=False, window_size=(600, 900), zoom_level=85)
    """
    options = webdriver.ChromeOptions()

    # Fenstergröße setzen
    options.add_argument(f'--window-size={window_size[0]},{window_size[1]}')

    if headless:
        # Headless-Modus aktivieren
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')

    # Bot-Erkennung umgehen
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    # User-Agent setzen
    options.add_argument(
        'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    )

    # WebDriver initialisieren
    driver = webdriver.Chrome(options=options)

    # Zoom-Level setzen (falls nicht 100%)
    if zoom_level != 100:
        driver.execute_script(f"document.body.style.zoom='{zoom_level}%'")

    return driver


def handle_cookiewall(driver, timeout=10):
    """
    Behandelt die Cookie-Wall durch Klicken des Accept-Buttons

    Args:
        driver: Selenium WebDriver Instanz
        timeout (int): Wartezeit in Sekunden

    Returns:
        bool: True wenn Cookie-Wall gefunden und akzeptiert, False sonst
    """
    try:
        wait = WebDriverWait(driver, timeout)
        # Warte auf den Cookie-Wall Accept-Button mit den spezifischen Klassen
        accept_button = wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "button.btn.btn--success.js-accept-basic")
            )
        )
        print("✓ Cookie-Wall gefunden - Klicke 'Accept'...")
        accept_button.click()
        time.sleep(1)  # Kurze Pause nach dem Klick
        print("✓ Cookie-Wall akzeptiert")
        return True
    except TimeoutException:
        print("⚠ Cookie-Wall nicht gefunden (möglicherweise bereits akzeptiert)")
        return False


def handle_consent_dialog(driver, timeout=10):
    """
    Behandelt den Consent-Dialog, der in einem iframe/frame erscheinen kann

    Args:
        driver: Selenium WebDriver Instanz
        timeout (int): Wartezeit in Sekunden

    Returns:
        bool: True wenn Consent-Dialog gefunden und akzeptiert, False sonst
    """
    try:
        # Suche nach iframe mit Consent-Dialog
        iframes = driver.find_elements(By.TAG_NAME, "iframe")

        for iframe in iframes:
            try:
                driver.switch_to.frame(iframe)

                # Suche nach Accept-Buttons mit verschiedenen möglichen Texten
                accept_texts = [
                    "Accept and continue",
                    "Accepteren en doorgaan",
                    "Ich akzeptiere die Datenschutzeinstellung",
                    "Accetto le impostazioni sulla privacy",
                    "Aceptar y continuar"
                ]

                for text in accept_texts:
                    try:
                        # Suche nach Button mit dem entsprechenden Text
                        button = driver.find_element(
                            By.XPATH,
                            f"//button[contains(text(), '{text}')]"
                        )
                        print(f"✓ Consent-Dialog gefunden ('{text}') - Klicke Accept...")
                        button.click()
                        time.sleep(1)
                        driver.switch_to.default_content()
                        print("✓ Consent-Dialog akzeptiert")
                        return True
                    except NoSuchElementException:
                        continue

                # Zurück zum Hauptdokument falls nichts gefunden
                driver.switch_to.default_content()
            except Exception:
                driver.switch_to.default_content()
                continue

        print("⚠ Consent-Dialog nicht gefunden (erscheint möglicherweise nicht)")
        return False

    except Exception as e:
        print(f"⚠ Fehler beim Behandeln des Consent-Dialogs: {e}")
        driver.switch_to.default_content()
        return False


def accept_cookies_and_consent(driver, wait_time=2, timeout=10, use_tracking=True, tracker=None):
    """
    Hauptfunktion: Behandelt sowohl Cookie-Wall als auch Consent-Dialog
    Mit optionalem Multi-Domain Tracking zur Vermeidung doppelter Behandlung

    Args:
        driver: Selenium WebDriver Instanz
        wait_time (int): Wartezeit in Sekunden zwischen den Aktionen
        timeout (int): Wartezeit für einzelne Elemente
        use_tracking (bool): Aktiviert/Deaktiviert Multi-Domain Tracking
        tracker (CookieTracker): Optional - eigene Tracker-Instanz

    Returns:
        dict: Status-Dictionary mit Informationen über erfolgte Aktionen
              {
                  'cookiewall_handled': bool,
                  'consent_handled': bool,
                  'was_already_handled': bool,
                  'url': str
              }

    Example:
        driver = setup_driver(headless=False)
        driver.get("https://www.tournamentsoftware.com")
        result = accept_cookies_and_consent(driver, use_tracking=True)
    """
    current_url = driver.current_url

    result = {
        'cookiewall_handled': False,
        'consent_handled': False,
        'was_already_handled': False,
        'url': current_url
    }

    # Tracker initialisieren
    if use_tracking:
        if tracker is None:
            tracker = get_tracker()

        # Prüfen, ob bereits behandelt
        if tracker.is_handled(current_url, 'both'):
            print(f"ℹ Domain bereits behandelt (Cookie-Wall & Consent) - Überspringe")
            result['was_already_handled'] = True
            result['cookiewall_handled'] = True
            result['consent_handled'] = True
            return result

    # Initiale Wartezeit für Seitenladevorgang
    time.sleep(wait_time)

    # Cookie-Wall behandeln
    cookiewall_found = handle_cookiewall(driver, timeout)
    result['cookiewall_handled'] = cookiewall_found

    # Kurze Pause zwischen den Aktionen
    time.sleep(1)

    # Consent-Dialog behandeln
    consent_found = handle_consent_dialog(driver, timeout)
    result['consent_handled'] = consent_found

    # Tracking aktualisieren
    if use_tracking and (cookiewall_found or consent_found):
        tracker.mark_handled(current_url, cookiewall_found, consent_found)
        print(f"✓ Tracking aktualisiert für {urlparse(current_url).netloc}")

    # Finale Wartezeit für vollständiges Laden
    time.sleep(wait_time)

    return result


def get_body_lines(driver, num_lines=5):
    """
    Extrahiert die ersten N Zeilen des HTML Body-Elements

    Args:
        driver: Selenium WebDriver Instanz
        num_lines (int): Anzahl der zu extrahierenden Zeilen

    Returns:
        list: Liste der ersten N Zeilen als Strings

    Example:
        lines = get_body_lines(driver, 5)
        for i, line in enumerate(lines, 1):
            print(f"{i}: {line}")
    """
    page_source = driver.page_source
    soup = BeautifulSoup(page_source, 'html.parser')

    body = soup.find('body')

    if body:
        body_html = body.prettify()
        lines = body_html.split('\n')
        return lines[:num_lines]
    else:
        return []


# Beispiel-Verwendung / Test
def _demo_multi_domain_scraping():
    """
    Demo-Funktion: Zeigt Multi-Domain Tracking in Aktion
    """
    driver = None
    tracker = get_tracker()

    # URLs zum Testen (mehrfache Zugriffe auf gleiche Domain)
    test_urls = [
        "https://www.tournamentsoftware.com",
        "https://www.tournamentsoftware.com/tournaments",
        "https://www.tournamentsoftware.com/leagues",
    ]

    try:
        print("→ Starte Chrome WebDriver...")
        driver = setup_driver(headless=False, window_size=(600, 900), zoom_level=85)

        for i, url in enumerate(test_urls, 1):
            print(f"\n{'=' * 70}")
            print(f"ZUGRIFF {i}/{len(test_urls)}: {url}")
            print('=' * 70)

            driver.get(url)

            # Mit Tracking
            result = accept_cookies_and_consent(driver, use_tracking=True)

            print(f"\nErgebnis:")
            print(f"  - Cookie-Wall behandelt: {result['cookiewall_handled']}")
            print(f"  - Consent behandelt: {result['consent_handled']}")
            print(f"  - War bereits behandelt: {result['was_already_handled']}")

            time.sleep(2)  # Kurze Pause zwischen URLs

        # Tracking-Status anzeigen
        print(f"\n{'=' * 70}")
        print("TRACKING-STATUS:")
        print('=' * 70)
        status = tracker.get_status()
        print(json.dumps(status, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"❌ Fehler: {e}")
        import traceback
        traceback.print_exc()

    finally:
        if driver:
            print("\n→ Schließe Browser...")
            driver.quit()
            print("✓ Fertig!")


#if __name__ == "__main__":
#    _demo_multi_domain_scraping()









"""
cookie_and_consent_handler.py:
Cookie-Wall und Consent-Dialog Handler für tournamentsoftware.com
Wiederverwendbares Modul für Web-Scraping mit Selenium
Verwendung:
    from cookie_and_consent_handler import setup_driver, accept_cookies_and_consent

    driver = setup_driver(headless=False, window_size=(1920, 1080), zoom_level=100)
    driver.get("https://www.tournamentsoftware.com/tournament/...")
    accept_cookies_and_consent(driver)
    # ... weitere Operationen
    driver.quit()
"""


'''
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
import time


def setup_driver(headless=True, window_size=(1920, 1080), zoom_level=100):
    """
    Initialisiert und konfiguriert einen Chrome WebDriver

    Args:
        headless (bool): True für Headless-Modus, False für sichtbaren Browser
        window_size (tuple): Fenstergröße als (breite, höhe) in Pixeln
        zoom_level (int): Zoom-Level in Prozent (z.B. 85 für 85%)

    Returns:
        webdriver.Chrome: Konfigurierter Chrome WebDriver

    Example:
        driver = setup_driver(headless=False, window_size=(600, 900), zoom_level=85)
    """
    options = webdriver.ChromeOptions()

    # Fenstergröße setzen
    options.add_argument(f'--window-size={window_size[0]},{window_size[1]}')

    if headless:
        # Headless-Modus aktivieren
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')

    # Bot-Erkennung umgehen
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    # User-Agent setzen
    options.add_argument(
        'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    )

    # WebDriver initialisieren
    driver = webdriver.Chrome(options=options)

    # Zoom-Level setzen (falls nicht 100%)
    if zoom_level != 100:
        driver.execute_script(f"document.body.style.zoom='{zoom_level}%'")

    return driver


def handle_cookiewall(driver, timeout=10):
    """
    Behandelt die Cookie-Wall durch Klicken des Accept-Buttons

    Args:
        driver: Selenium WebDriver Instanz
        timeout (int): Wartezeit in Sekunden

    Returns:
        bool: True wenn Cookie-Wall gefunden und akzeptiert, False sonst
    """
    try:
        wait = WebDriverWait(driver, timeout)
        # Warte auf den Cookie-Wall Accept-Button mit den spezifischen Klassen
        accept_button = wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "button.btn.btn--success.js-accept-basic")
            )
        )
        print("✓ Cookie-Wall gefunden - Klicke 'Accept'...")
        accept_button.click()
        time.sleep(1)  # Kurze Pause nach dem Klick
        print("✓ Cookie-Wall akzeptiert")
        return True
    except TimeoutException:
        print("⚠ Cookie-Wall nicht gefunden (möglicherweise bereits akzeptiert)")
        return False


def handle_consent_dialog(driver, timeout=10):
    """
    Behandelt den Consent-Dialog, der in einem iframe/frame erscheinen kann

    Args:
        driver: Selenium WebDriver Instanz
        timeout (int): Wartezeit in Sekunden

    Returns:
        bool: True wenn Consent-Dialog gefunden und akzeptiert, False sonst
    """
    try:
        # Suche nach iframe mit Consent-Dialog
        iframes = driver.find_elements(By.TAG_NAME, "iframe")

        for iframe in iframes:
            try:
                driver.switch_to.frame(iframe)

                # Suche nach Accept-Buttons mit verschiedenen möglichen Texten
                accept_texts = [
                    "Accept and continue",
                    "Accepteren en doorgaan",
                    "Ich akzeptiere die Datenschutzeinstellung",
                    "Accetto le impostazioni sulla privacy",
                    "Aceptar y continuar"
                ]

                for text in accept_texts:
                    try:
                        # Suche nach Button mit dem entsprechenden Text
                        button = driver.find_element(
                            By.XPATH,
                            f"//button[contains(text(), '{text}')]"
                        )
                        print(f"✓ Consent-Dialog gefunden ('{text}') - Klicke Accept...")
                        button.click()
                        time.sleep(1)
                        driver.switch_to.default_content()
                        print("✓ Consent-Dialog akzeptiert")
                        return True
                    except NoSuchElementException:
                        continue

                # Zurück zum Hauptdokument falls nichts gefunden
                driver.switch_to.default_content()
            except Exception:
                driver.switch_to.default_content()
                continue

        print("⚠ Consent-Dialog nicht gefunden (erscheint möglicherweise nicht)")
        return False

    except Exception as e:
        print(f"⚠ Fehler beim Behandeln des Consent-Dialogs: {e}")
        driver.switch_to.default_content()
        return False


def accept_cookies_and_consent(driver, wait_time=2, timeout=10):
    """
    Hauptfunktion: Behandelt sowohl Cookie-Wall als auch Consent-Dialog

    Args:
        driver: Selenium WebDriver Instanz
        wait_time (int): Wartezeit in Sekunden zwischen den Aktionen
        timeout (int): Wartezeit für einzelne Elemente

    Returns:
        dict: Status-Dictionary mit Informationen über erfolgte Aktionen
              {'cookiewall_handled': bool, 'consent_handled': bool}

    Example:
        driver = setup_driver(headless=False)
        driver.get("https://www.tournamentsoftware.com")
        result = accept_cookies_and_consent(driver)
    """
    result = {
        'cookiewall_handled': False,
        'consent_handled': False
    }

    # Initiale Wartezeit für Seitenladevorgang
    time.sleep(wait_time)

    # Cookie-Wall behandeln
    result['cookiewall_handled'] = handle_cookiewall(driver, timeout)

    # Kurze Pause zwischen den Aktionen
    time.sleep(1)

    # Consent-Dialog behandeln
    result['consent_handled'] = handle_consent_dialog(driver, timeout)

    # Finale Wartezeit für vollständiges Laden
    time.sleep(wait_time)

    return result


def get_body_lines(driver, num_lines=5):
    """
    Extrahiert die ersten N Zeilen des HTML Body-Elements

    Args:
        driver: Selenium WebDriver Instanz
        num_lines (int): Anzahl der zu extrahierenden Zeilen

    Returns:
        list: Liste der ersten N Zeilen als Strings

    Example:
        lines = get_body_lines(driver, 5)
        for i, line in enumerate(lines, 1):
            print(f"{i}: {line}")
    """
    page_source = driver.page_source
    soup = BeautifulSoup(page_source, 'html.parser')

    body = soup.find('body')

    if body:
        body_html = body.prettify()
        lines = body_html.split('\n')
        return lines[:num_lines]
    else:
        return []


# Beispiel-Verwendung / Test
def _demo_scrape_tournamentsoftware():
    """
    Demo-Funktion zur Veranschaulichung der Verwendung
    """
    driver = None

    try:
        # WebDriver initialisieren
        print("→ Starte Chrome WebDriver...")
        driver = setup_driver(headless=False, window_size=(600, 900), zoom_level=85)

        # Seite aufrufen
        url = "https://www.tournamentsoftware.com"
        print(f"→ Rufe URL auf: {url}")
        driver.get(url)

        # Cookies und Consent behandeln
        print("→ Behandle Cookie-Wall und Consent-Dialog...")
        result = accept_cookies_and_consent(driver)

        print(f"\nErgebnis: {result}")

        # Erste 5 Zeilen des Body extrahieren
        lines = get_body_lines(driver, 100)

        if lines:
            print("\n" + "="*70)
            print("ERSTE ZEILEN VOM HTML <BODY>:")
            print("="*70)

            for i, line in enumerate(lines, 1):
                print(f"{i}: {line}")

            print("="*70)
        else:
            print("⚠ Kein <body>-Element gefunden!")

    except Exception as e:
        print(f"❌ Fehler: {e}")
        import traceback
        traceback.print_exc()

    finally:
        if driver:
            print("\n→ Schließe Browser...")
            driver.quit()
            print("✓ Fertig!")


if __name__ == "__main__":
    _demo_scrape_tournamentsoftware()
'''