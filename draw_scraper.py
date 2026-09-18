"""
Draw Scraper für tournamentsoftware.com
Findet relevante Draw-Links (JE/ME U15)

TODO (Phase 2, BEC U17): 1:1 aus bec_u15_auswertung übernommen, deckt bislang nur Einzel (JE/ME)
ab. Für BEC U17 sollen laut Planung auch Doppel/Mixed erfasst werden -- find_draw_links()/
scrape_all_draws() müssen um JD/MD/XD-Tag-Varianten (z.B. "Boys Doubles", "BD", "Jungendoppel")
erweitert werden, analog zu den bestehenden JE/ME-Pattern-Listen.
"""
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import re
import time
from player_in_list import split_match_name, player_in_list



def find_draw_links(driver, tournament_id, discipline='JE', age_group='U15', timeout=15):
    """
    Findet alle Draw-Links für eine bestimmte Disziplin und Altersklasse

    Args:
        driver: Selenium WebDriver
        tournament_id: ID des Turniers
        discipline: 'JE' oder 'ME'
        age_group: z.B. 'U15' (kann None sein für alle Altersklassen)
        timeout: Wartezeit

    Returns:
        Liste von Tuples: [(draw_name, draw_url), ...]
    """
    draw_links = []

    try:
        # Import hier um zirkuläre Abhängigkeiten zu vermeiden
        from cookie_handler import accept_cookies_and_consent

        # URL zum Draws-Tab
        draws_url = f"https://www.tournamentsoftware.com/sport/draws.aspx?id={tournament_id}"
        print(f"\n→ Lade Draws-Seite: {draws_url}")
        driver.get(draws_url)

        # Cookie-Dialoge behandeln (falls neue Domain)
        accept_cookies_and_consent(driver)

        # Warte auf Tabelle mit Draws
        wait = WebDriverWait(driver, timeout)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.ruler")))
        time.sleep(1)

        # Hauptkürzel für diese Disziplin
        if discipline == 'JE':
            base_tags = ["JE", "MS", "BS", "HS"]  # verschiedene Boys-Singles Kürzel
            lang_tags = [
                r'Boys?\s+Singles?', r'Jungeneinzel', r'Garçons\s+Simple'
            ]
        elif discipline == 'ME':
            base_tags = ["ME", "WS", "GS", "DS"]  # verschiedene Girls-Singles Kürzel
            lang_tags = [
                r'Girls?\s+Singles?', r'Mädcheneinzel', r'Filles\s+Simple'
            ]
        else:
            print(f"✗ Unbekannte Disziplin: {discipline}")
            return []

        # Regex-Liste erzeugen
        patterns = []

        # 1) Basis-Kürzel (JE, ME, MS, WS, etc)
        for tag in base_tags:
            patterns.append(rf'\b{tag}\b')  # MS
            patterns.append(rf'\b{tag}\s*U?{age_group}\b')  # MSU15 oder MS U15

        # 2) Sprachvarianten
        patterns.extend(lang_tags)


        '''
        # Pattern für die Disziplin
        if discipline == 'JE':
            # Jungeneinzel: JE, MS, BS, HS, Boys Singles, Jungeneinzel
            patterns = [
                r'\bJE\b', r'\bMS\b', r'\bBS\b', r'\bHS\b', # dänisch
                r'Boys?\s+Singles?', r'Jungeneinzel',
                r'Garçons\s+Simple'  # Französisch
            ]
        elif discipline == 'ME':
            # Mädcheneinzel: ME, WS, GS, DS, Girls Singles, Mädcheneinzel
            patterns = [
                r'\bME\b', r'\bWS\b', r'\bGS\b', r'\bDS\b', # dänisch
                r'Girls?\s+Singles?', r'Mädcheneinzel',
                r'Filles\s+Simple'  # Französisch
            ]
        else:
            print(f"✗ Unbekannte Disziplin: {discipline}")
            return []
        '''





        # Altersgruppe Pattern (optional)
        age_pattern = re.compile(rf'\b{age_group}\b', re.IGNORECASE) if age_group else None

        # Alle Links in der Tabelle finden
        all_links = driver.find_elements(By.CSS_SELECTOR, "table.ruler a[href*='draw']")
        print(f"   Gefundene Draw-Links gesamt: {len(all_links)}")

        # Zähle wie viele Draws die Altersgruppe explizit enthalten
        draws_with_age = 0
        draws_without_age = []

        for link in all_links:
            try:
                draw_name = link.text.strip()
                draw_url = link.get_attribute('href')

                # Prüfe ob Disziplin passt
                matches_discipline = False
                for pattern in patterns:
                    if re.search(pattern, draw_name, re.IGNORECASE):
                        matches_discipline = True
                        break

                if not matches_discipline:
                    continue

                # Prüfe ob Altersgruppe vorhanden ist
                has_age_group = age_pattern.search(draw_name) if age_pattern else False

                if has_age_group:
                    draws_with_age += 1
                    draw_links.append((draw_name, draw_url))
                    print(f"   ✓ Gefunden: {draw_name}")
                else:
                    # Merke Draws ohne Altersangabe
                    draws_without_age.append((draw_name, draw_url))

            except Exception as e:
                continue

        # Wenn KEINE Draws die Altersgruppe enthalten, akzeptiere ALLE Draws dieser Disziplin
        # (z.B. reines U15-Turnier wo "U15" nirgends steht)
        if draws_with_age == 0 and draws_without_age:
            print(f"   ℹ Keine Draws mit '{age_group}' gefunden - akzeptiere alle {discipline} Draws")
            for draw_name, draw_url in draws_without_age:
                draw_links.append((draw_name, draw_url))
                print(f"   ✓ Gefunden: {draw_name}")

        print(f"   → {len(draw_links)} relevante Draws gefunden für {discipline} {age_group}")
        return draw_links

    except Exception as e:
        print(f"✗ Fehler beim Suchen der Draws: {e}")
        return []


def scrape_all_draws(driver, tournament_id, age_group='U15'):
    """
    Findet alle JE und ME Draws für ein Turnier

    Args:
        driver: Selenium WebDriver
        tournament_id: ID des Turniers
        age_group: z.B. 'U15'

    Returns:
        dict: {'JE': [(name, url), ...], 'ME': [(name, url), ...]}
    """
    result = {
        'JE': [],
        'ME': []
    }

    print(f"\n{'='*60}")
    print(f"Suche Draws für {age_group}")
    print(f"{'='*60}")

    # Jungeneinzel
    print(f"\n--- Jungeneinzel ({age_group}) ---")
    result['JE'] = find_draw_links(driver, tournament_id, 'JE', age_group)

    # Mädcheneinzel
    print(f"\n--- Mädcheneinzel ({age_group}) ---")
    result['ME'] = find_draw_links(driver, tournament_id, 'ME', age_group)

    return result