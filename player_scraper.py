"""
Player Scraper für tournamentsoftware.com
Extrahiert Spielerliste vom Players-Tab
"""
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import re
import time
from urllib.parse import urljoin


def extract_players_from_page(driver, timeout=15):
    """
    Extrahiert alle Spieler vom Players-Tab.

    Unterstützt:
      • normale Seitenstruktur mit <ol class="player-list js-alphabet-list">
      • Turniere mit Buchstabenabschnitten (<li class="player-list__cat"> mit eigenen <ol>)
        → z.B. Polish Open

    Args:
        driver: Selenium WebDriver (bereits auf Players-Seite)
        timeout: Wartezeit

    Returns:
        Liste von dicts: {'name': str, 'vorname': str, 'club': str, 'nation': str}
    """
    players = []

    try:
        wait = WebDriverWait(driver, timeout)

        # Sicherstellen, dass Seite geladen ist
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        print("→ Seite geladen")
        time.sleep(1)

        # --- NEU: Erfasse alle relevanten <ol>-Container ---
        main_ols = driver.find_elements(By.CSS_SELECTOR, "ol.player-list.js-alphabet-list")
        cats = driver.find_elements(By.CSS_SELECTOR, "li.player-list__cat")

        print(f"→ Haupt-OLs: {len(main_ols)},  Buchstabenabschnitte: {len(cats)}")

        all_ols = []

        # Wenn es Buchstabenabschnitte gibt, verwende nur diese – sonst die Hauptliste
        if cats:
            print("→ Verwende Buchstabenabschnitte (mehrere OLs erkannt)")
            for cat in cats:
                sub_ols = cat.find_elements(By.CSS_SELECTOR, "ol.list.list--grid")
                if sub_ols:
                    all_ols.extend(sub_ols)
        else:
            print("→ Verwende Hauptliste (eine OL erkannt)")
            all_ols.extend(main_ols)

        print(f"→ Gesamt-OLs zur Auswertung: {len(all_ols)}")
        # triggert das Rendering (lazy loading)
        for ol in all_ols:
            driver.execute_script("arguments[0].scrollIntoView(true);", ol)
            time.sleep(0.3)

        # Innerhalb dieser OLs nach Player-Containern suchen
        player_items = []
        for ol in all_ols:
            divs = ol.find_elements(By.CSS_SELECTOR, "div.media__content")
            player_items.extend(divs)

        print(f"   Gefundene Player-Container gesamt: {len(player_items)}")

        # --- Spieler-Daten auslesen ---
        for item in player_items:
            try:
                # Nation (Flagge)
                nation = ""
                try:
                    flag_img = item.find_element(By.CSS_SELECTOR, "img.icon-lang")
                    flag_src = flag_img.get_attribute("src") or ""
                    match = re.search(r"/flags/([A-Z]{3})\.svg", flag_src)
                    if match:
                        nation = match.group(1)
                    else:
                        alt = flag_img.get_attribute("alt") or ""
                        if alt and len(alt.strip()) == 3:
                            nation = alt.strip()
                except Exception:
                    nation = ""

                # Name (Nachname, Vorname)
                full_name = ""
                try:
                    name_element = item.find_element(By.CSS_SELECTOR, "h5.media__title a span.nav-link__value")
                    full_name = name_element.text.strip()
                except Exception:
                    try:
                        name_element = item.find_element(By.CSS_SELECTOR, "h5.media__title a")
                        full_name = name_element.text.strip()
                    except Exception:
                        full_name = ""

                name = ""
                vorname = ""
                if "," in full_name:
                    parts = full_name.split(",", 1)
                    name = parts[0].strip()
                    vorname = parts[1].strip()
                else:
                    parts = full_name.split(" ", 1)
                    if len(parts) == 2:
                        vorname = parts[0].strip()
                        name = parts[1].strip()
                    else:
                        name = full_name.strip()

                # Club / Verein
                club = ""
                try:
                    subinfo_div = item.find_element(By.CSS_SELECTOR, "div.media__content-subinfo")
                    sub_spans = subinfo_div.find_elements(By.CSS_SELECTOR, "span.nav-link__value")
                    for s in sub_spans:
                        txt = s.text.strip()
                        if txt:
                            club = txt
                            break
                except Exception:
                    club = ""

                players.append({
                    "name": name,
                    "vorname": vorname,
                    "club": club,
                    "nation": nation
                })

            except Exception as e:
                print(f"⚠ Fehler beim Extrahieren eines Spielers: {e}")
                continue

        print(f"✓ {len(players)} Spieler erfolgreich extrahiert")
        '''
        non_empty = [p for p in players if p.get('name')]
        print(f"→ Gefüllt: {len(non_empty)} / {len(players)} Spieler haben Namen")
        if len(non_empty) < len(players):
            print("⚠️ Ab hier leere Datensätze (z. B.):")
            for i, p in enumerate(players):
                if not p.get('name'):
                    print(f"  Index {i}: {p}")
                    break
        '''
        return players

    except Exception as e:
        print(f"✗ Fehler beim Extrahieren der Spielerliste: {e}")
        import traceback
        traceback.print_exc()
        return []


'''
def extract_players_from_page(driver, timeout=15):
    """
    Extrahiert alle Spieler vom Players-Tab innerhalb des
    <ol class="player-list js-alphabet-list">.

    Args:
        driver: Selenium WebDriver (bereits auf Players-Seite)
        timeout: Wartezeit

    Returns:
        Liste von dicts: {'name': str, 'vorname': str, 'club': str, 'nation': str}
    """
    players = []
    try:
        wait = WebDriverWait(driver, timeout)

        # Warten bis Body und Players-Liste geladen sind
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        print("→ Seite geladen")

        # Warte auf die eigentliche Liste
        ol = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "ol.player-list.js-alphabet-list"))
        )
        print("→ Player-Liste gefunden")

        time.sleep(1.5)  # etwas Zeit für dynamische Inhalte

        # Alle Player-Container im <ol> suchen
        player_divs = ol.find_elements(By.CSS_SELECTOR, "div.media__content")
        print(f"   Gefundene Player-Container: {len(player_divs)}")

        for div in player_divs:
            try:
                # Nation / Flagge
                nation = ""
                try:
                    flag_img = div.find_element(By.CSS_SELECTOR, "img.icon-lang")
                    flag_src = flag_img.get_attribute("src") or ""
                    m = re.search(r"/flags/([A-Z]{3})\.svg", flag_src)
                    if m:
                        nation = m.group(1)
                    else:
                        alt = flag_img.get_attribute("alt") or ""
                        if alt and len(alt.strip()) == 3:
                            nation = alt.strip()
                except Exception:
                    nation = ""

                # Name: <h5 class="media__title"> … <span class="nav-link__value">Nachname, Vorname</span>
                full_name = ""
                try:
                    name_elem = div.find_element(
                        By.CSS_SELECTOR, "h5.media__title a.nav-link.media__link span.nav-link__value"
                    )
                    full_name = name_elem.text.strip()
                except Exception:
                    try:
                        a = div.find_element(By.CSS_SELECTOR, "h5.media__title a")
                        full_name = a.text.strip()
                    except Exception:
                        full_name = ""

                # Name/Vorname aufteilen
                name = ""
                vorname = ""
                if "," in full_name:
                    parts = full_name.split(",", 1)
                    name = parts[0].strip()
                    vorname = parts[1].strip()
                else:
                    parts = full_name.split(" ", 1)
                    if len(parts) == 2:
                        vorname, name = parts[0].strip(), parts[1].strip()
                    else:
                        name = full_name.strip()

                # Club / Verein: erstes nicht-leeres span.nav-link__value in div.media__content-subinfo
                club = ""
                try:
                    subinfo = div.find_element(By.CSS_SELECTOR, "div.media__content-subinfo")
                    spans = subinfo.find_elements(By.CSS_SELECTOR, "span.nav-link__value")
                    for s in spans:
                        txt = s.text.strip()
                        if txt:
                            club = txt
                            break
                except Exception:
                    club = ""

                players.append({
                    "name": name,
                    "vorname": vorname,
                    "club": club,
                    "nation": nation
                })
                print(name, vorname, club, nation)

            except Exception as e:
                print(f"   ⚠ Fehler beim Extrahieren eines Players: {e}")
                continue

        print(f"   ✓ {len(players)} Spieler erfolgreich extrahiert")
        return players

    except Exception as e:
        print(f"✗ Fehler beim Extrahieren der Spielerliste: {e}")
        import traceback
        traceback.print_exc()
        return []
'''


def scrape_players(driver, tournament_id):
    """
    Navigiert zum Players-Tab und extrahiert alle Spieler

    Args:
        driver: Selenium WebDriver
        tournament_id: ID des Turniers (aus URL)

    Returns:
        Liste von Spieler-Dicts
    """
    try:
        # Import hier um zirkuläre Abhängigkeiten zu vermeiden
        from cookie_handler import accept_cookies_and_consent

        # URL zum Players-Tab
        players_url = f"https://www.tournamentsoftware.com/tournament/{tournament_id}/players"
        print(f"\n→ Lade Players-Seite: {players_url}")
        driver.get(players_url)

        # Cookie-Dialoge behandeln (falls neue Domain)
        accept_cookies_and_consent(driver, reload_after=False)

        # Normale Reload (für nicht-Polish Turniere)
        print("   → Lade Seite neu nach Cookie-Handling...")
        driver.get(players_url)
        time.sleep(3)
        print("   ✓ Seite neu geladen")

        # Spieler extrahieren
        players = extract_players_from_page(driver)
        return players

    except Exception as e:
        print(f"✗ Fehler beim Scrapen der Spieler: {e}")
        import traceback
        traceback.print_exc()
        return []


def scrape_players_v2(driver, tournament_url, tournament_id, timeout=10):
    """
    Finds the players.aspx link in the current tournament page HTML that matches
    '<a href="/sport/players.aspx?id=<tournament_id>..."', follows it, prints the players URL,
    then on the players page finds the first player container inside
    <ol class="player-list js-alphabet-list"> and prints/returns:
      - nation (3-letter code from flag src or alt)
      - name ("Nachname, Vorname")
      - club (first non-empty span.nav-link__value in subinfo)

    Args:
        driver: Selenium WebDriver (already able to open tournament_url)
        tournament_url: full URL of tournament main page (string)
        tournament_id: tournament ID from URL (string)
        timeout: wait timeout in seconds

    Returns:
        dict with keys: {"players_url","nation","name","club"} or None on fatal error
    """

    try:
        from cookie_handler import accept_cookies_and_consent

        driver.get(tournament_url)
        accept_cookies_and_consent(driver, reload_after=False)

        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        time.sleep(0.5)

        page_html = driver.page_source

        # ----------------------------------------------
        # 1) Primär: Klassisches Muster players.aspx?id=<tournament_id>
        # ----------------------------------------------
        pattern = rf'href\s*=\s*"(\/sport\/players\.aspx\?id={re.escape(tournament_id)}[^"]*)"'
        m = re.search(pattern, page_html, re.IGNORECASE)

        if m:
            href_rel = m.group(1)
            print("✓ Players-Link (klassisch) gefunden:")
        else:
            print("✗ Kein klassischer Players-Link gefunden.")

            # ----------------------------------------------
            # 2) Fallback: allgemeines players.aspx (ohne id)
            # ----------------------------------------------
            m_loose = re.search(r'href\s*=\s*"(\/sport\/players\.aspx[^"]*)"', page_html, re.IGNORECASE)
            if m_loose:
                href_rel = m_loose.group(1)
                print("ℹ Fallback: allgemeiner players.aspx-Link gefunden.")

            else:
                print("✗ Auch kein players.aspx-Link gefunden.")

                # ----------------------------------------------
                # 3) NEUER Fallback: Badminton Sweden Muster
                #    /tournament/<ID>/players
                # ----------------------------------------------
                pattern_sweden = rf'href\s*=\s*"(\/tournament\/{re.escape(tournament_id)}\/players[^"]*)"'
                m_sweden = re.search(pattern_sweden, page_html, re.IGNORECASE)

                if m_sweden:
                    href_rel = m_sweden.group(1)
                    print("✓ Neuer Fallback-Treffer: Sweden-Players-Seite erkannt.")
                else:
                    print("✗ Keine Players-Seite gefunden – auch nicht im Sweden-Format.")
                    return None

        players_url = urljoin(tournament_url, href_rel)
        print(f"→ Players-Seite: {players_url}")

        # 3) Players-Seite öffnen
        driver.get(players_url)
        accept_cookies_and_consent(driver, reload_after=False)
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        time.sleep(1.0)

        players = extract_players_from_page(driver)
        return players

    except Exception as e:
        print(f"✗ Fehler in scrape_players_v2: {e}")
        import traceback
        traceback.print_exc()
        return None


    '''
    try:
        # Import hier um zirkuläre Abhängigkeiten zu vermeiden
        from cookie_handler import accept_cookies_and_consent

        # 1) Ensure tournament page is loaded in driver
        driver.get(tournament_url)
        # Cookie-Dialoge behandeln (falls neue Domain)
        accept_cookies_and_consent(driver, reload_after=False)

        WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(0.5)

        # 2) Search the page_source for the exact players href pattern (per requirement)
        page_html = driver.page_source
        # pattern: href="/sport/players.aspx?id=<tournament_id>..." (allow additional query params)
        pattern = rf'href\s*=\s*"(\/sport\/players\.aspx\?id={re.escape(tournament_id)}[^"]*)"'
        m = re.search(pattern, page_html, re.IGNORECASE)
        if not m:
            print("✗ Kein Players-Link mit dem erwarteten Muster im HTML gefunden.")
            # optional: try a looser search for players.aspx
            m_loose = re.search(r'href\s*=\s*"(\/sport\/players\.aspx[^"]*)"', page_html, re.IGNORECASE)
            if m_loose:
                href_rel = m_loose.group(1)
                print("  ℹ Fallback: allgemeiner players.aspx Link gefunden (ohne id-filter).")
            else:
                return None
        else:
            href_rel = m.group(1)

        # Build absolute URL (href_rel may be relative)
        players_url = urljoin(tournament_url, href_rel)
        print(f"✓ Players-Seite gefunden: {players_url}")

        # 3) Open players page
        driver.get(players_url)
        # Cookie-Dialoge behandeln (falls neue Domain)
        accept_cookies_and_consent(driver, reload_after=False)
        WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(1.0)  # give AJAX a moment
        players = extract_players_from_page(driver)
        return players

    except Exception as e:
        print(f"✗ Fehler in scrape_players_v2: {e}")
        import traceback
        traceback.print_exc()
        return None
'''

    '''
    try:
        # Import hier um zirkuläre Abhängigkeiten zu vermeiden
        from cookie_handler import accept_cookies_and_consent

        # URL zum Players-Tab
        players_url = f"https://www.tournamentsoftware.com/tournament/{tournament_id}/players"
        print(f"\n→ Lade Players-Seite: {players_url}")
        driver.get(players_url)

        # Cookie-Dialoge behandeln (falls neue Domain)
        accept_cookies_and_consent(driver, reload_after=False)

        # Normale Reload (für nicht-Polish Turniere)
        print("   → Lade Seite neu nach Cookie-Handling...")
        driver.get(players_url)
        time.sleep(3)
        print("   ✓ Seite neu geladen")

        # Spieler extrahieren
        players = extract_players_from_page(driver)

        return players

    except Exception as e:
        print(f"✗ Fehler beim Scrapen der Spieler: {e}")
        import traceback
        traceback.print_exc()
        return []'''