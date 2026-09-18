# TODO (Phase 2, BEC U17): 1:1 aus bec_u15_auswertung übernommen, geht bislang von Einzel-Matches
# (ein Spieler je Seite) aus. Für Doppel/Mixed muss die Namensauflösung je Seite zwei Spieler
# (Partner) statt einem liefern -- passend zum neuen matches-Schema (heim_spieler1_id/
# heim_spieler2_id, analog gast_*), siehe schema.sql.
from bs4 import BeautifulSoup
import re
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from player_in_list import split_match_name, player_in_list
import time


def click_load_more(driver, timeout=10, max_clicks=20):
    """
    Klickt mehrfach auf 'Load more' (oder Sprachvarianten), bis keine mehr existieren.
    Unterstützt Lazy Loading (Scrollen + Warten auf AJAX).
    """
    click_count = 0
    while click_count < max_clicks:
        try:
            # Scroll an Seitenende, um den Button sichtbar zu machen
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.0)

            # Kandidaten über Text finden (case-insensitive über lower() in Python)
            btn_candidates = []
            all_buttons = driver.find_elements(By.TAG_NAME, "button")
            for b in all_buttons:
                txt = b.text.strip().lower()
                if any(k in txt for k in [
                    "load more", "mehr anzeigen", "afficher plus", "mostrar",
                    "visa mer", "vis flere", "carica", "więcej", "more"
                ]):
                    btn_candidates.append(b)

            # Fallback über CSS
            if not btn_candidates:
                btn_candidates = driver.find_elements(By.CSS_SELECTOR, ".load-more-btn-container button")

            if not btn_candidates:
                print("   ✓ Kein 'Load more'-Button mehr sichtbar.")
                break

            btn = btn_candidates[0]

            # Button sichtbar machen und klicken
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
            time.sleep(0.5)

            if btn.is_enabled() and btn.is_displayed():
                print(f"   → Klick #{click_count+1} auf 'Load more' ...")
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(2.5)  # Zeit für Nachladen
                click_count += 1

                # Debug: Prüfe, ob sich die Anzahl der Matches verändert
                matches_now = len(driver.find_elements(By.CSS_SELECTOR, "div.match"))
                print(f"      🔄 Aktuell geladene Matches: {matches_now}")
            else:
                print("   ⚠ 'Load more'-Button nicht klickbar (vermutlich Ende erreicht).")
                break

        except Exception as e:
            print(f"   ⚠ Kein weiterer 'Load more'-Button gefunden ({e})")
            break

    print(f"   ✓ 'Load more'-Routine abgeschlossen, {click_count} Klicks ausgeführt.")


def clean_name(name):
    """Entfernt Setzplatzinfos und trimmt."""
    return re.sub(r'\s*\[\d+/?\d*\]\s*', '', name).strip()

def split_name(fullname):
    """Teilt 'Vorname Nachname' in (Nachname, Vorname)."""
    parts = fullname.strip().split()
    if len(parts) >= 2:
        return parts[-1], " ".join(parts[:-1])
    return fullname, ""

def player_in_list(vorname, nachname, players):
    """Prüft, ob Spieler in Players-Liste vorkommt (case-insensitive)."""
    v = vorname.lower()
    n = nachname.lower()
    for p in players:
        if p["name"].lower() == n and p["vorname"].lower() == v:
            return True
    return False

def scrape_matches_from_draw(driver, draw_url, konkurrenz, players):
    """Extrahiert alle Matches eines Draws + ggf. Gruppen-Standing."""
    matches = []
    bye_count = 0
    group_standing = []

    try:
        # Seite laden
        driver.get(draw_url)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(2)

        click_load_more(driver)
        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")

        # --- 1️⃣ Versuche Gruppen-Standing zu erkennen ---
        standing_table = soup.find("table", class_="table--striped table--new")
        if standing_table:
            print("   ✓ Gruppen-Standing erkannt – extrahiere Platzierungen ...")
            for row in standing_table.find_all("tr"):
                pos_span = row.find("span", class_="standing-status")
                name_span = row.find("span", class_="nav-link__value")
                if pos_span and name_span:
                    pos = pos_span.text.strip()
                    name = name_span.text.strip()
                    if pos and name:
                        s_name, s_vorname = split_match_name(name, players)
                        group_standing.append((int(pos), s_name, s_vorname))
            print(f"   → Gefundene Platzierungen: {len(group_standing)}")
        else:
            print("   ⚠ Keine Gruppen-Tabelle gefunden (vermutlich KO-System).")

        # --- 2️⃣ Matches scrapen (bestehende Logik) ---
        # --- Nur Matches nach der Überschrift extrahieren ---
        marker_tag = '<span class="module__title-main">'
        pos_matches = html.lower().find(marker_tag)

        if pos_matches == -1:
            print("   ⚠ Kein eindeutiger Match-Abschnitt gefunden – verwende gesamte Seite")
            match_section = driver
        else:
            print(f"   ✓ Match-Abschnitt gefunden (Index {pos_matches})")

            try:
                match_section = driver.find_element(By.CSS_SELECTOR, "div#draw-matches.module.module--card")
            except Exception:
                try:
                    match_section = driver.find_element(By.CSS_SELECTOR, "span.module__title-main")
                    match_section = match_section.find_element(
                        By.XPATH, "./ancestor::div[contains(@class, 'module')][1]"
                    )
                except Exception as e:
                    print(f"   ⚠ Fallback fehlgeschlagen, verwende gesamte Seite: {e}")
                    match_section = driver

        # Sammle Match-Container
        try:
            match_rows = match_section.find_elements(
                By.CSS_SELECTOR, "ul.match-group li.match-group__item div.match"
            )
            if not match_rows:
                match_rows = match_section.find_elements(By.CSS_SELECTOR, "div.match")

            print(f"   → Gefundene potentielle Match-Container: {len(match_rows)}")

            real_matches = []
            for m in match_rows:
                try:
                    m.find_element(By.CSS_SELECTOR, ".match__header")
                    m.find_element(By.CSS_SELECTOR, ".match__body")
                    real_matches.append(m)
                except Exception:
                    continue
            match_rows = real_matches
            print(f"   → Davon echte Matches mit Inhalt: {len(match_rows)}")

        except Exception as e:
            print(f"   ⚠ Konnte Match-Container nicht finden: {e}")
            match_rows = []

        # --- Matches extrahieren ---
        matches = []
        bye_count = 0
        for row in match_rows:
            try:
                # Runde
                try:
                    round_elem = row.find_element(By.CSS_SELECTOR, ".match__header [title]")
                    runde = round_elem.get_attribute("title").strip()
                except Exception:
                    runde = ""

                player_elems = row.find_elements(By.CSS_SELECTOR, ".match__row-title-value-content")
                if len(player_elems) < 2:
                    continue
                home_elem, guest_elem = player_elems[:2]

                def get_name(elem):
                    try:
                        return elem.find_element(By.CSS_SELECTOR, "span.nav-link__value").text.strip()
                    except Exception:
                        return ""

                def get_nation(elem):
                    try:
                        img = elem.find_element(
                            By.XPATH,
                            "./preceding-sibling::span[contains(@class, 'match__row-title-prefix')]//img"
                        )
                        src = img.get_attribute("src") or ""
                        m = re.search(r"/flags/([A-Z]{3})\.svg", src)
                        if m:
                            return m.group(1)
                        return img.get_attribute("alt") or ""
                    except Exception:
                        return ""

                # ✅ Nationalitäten auslesen
                h_nation = get_nation(home_elem)
                g_nation = get_nation(guest_elem)

                home_full = get_name(home_elem)
                guest_full = get_name(guest_elem)

                if any(x in home_full.lower() or x in guest_full.lower()
                       for x in ("bye", "friplats")):
                    bye_count += 1
                    continue

                # Ergebnis
                ergebnis = ""
                try:
                    result_cells = row.find_elements(By.CSS_SELECTOR, ".match__result li.points__cell")
                    scores = [c.text.strip() for c in result_cells if c.text.strip()]
                    if scores:
                        sets = [f"{scores[i]}-{scores[i + 1]}" for i in range(0, len(scores), 2) if i + 1 < len(scores)]
                        ergebnis = " ".join(sets)
                except Exception:
                    pass

                h_name, h_vorname = split_match_name(home_full, players)
                g_name, g_vorname = split_match_name(guest_full, players)

                # ✅ Erweiterte Speicherung inklusive Nation
                matches.append((
                    konkurrenz,
                    runde,
                    h_name, h_vorname, h_nation,
                    g_name, g_vorname, g_nation,
                    ergebnis
                ))
            except Exception as e:
                print(f"   ⚠ Fehler beim Lesen eines Matches: {e}")
                continue

        print(f"   ✓ {len(matches)} Matches gefunden ({bye_count} Byes ignoriert)")
        return matches, bye_count, group_standing

    except Exception as e:
        print(f"✗ Fehler beim Extrahieren der Matches: {e}")
        return [], bye_count, group_standing
