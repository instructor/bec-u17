# CLAUDE.md

Projekt: BEC-U17-Auswertung. Berechnet aus den Ergebnissen des internationalen BEC-U17-Circuits
(Badminton Europe Circuit, Altersklasse U17) eine eigene Teilnehmer-Rangliste UND eine
Turnierstärke-Rangfolge -- analog zum Schwesterprojekt `../bec_u15_auswertung` (U15), aber mit
eigenem Schema/eigener DB (`u17_int.db`), da die Turnierstruktur (48 Einzelturniere über 2 Jahre
statt ~14 wiederkehrender Serien) andere Architekturentscheidungen braucht. Siehe auch
`../CLAUDE.md` (übergeordnetes Domänenmodell, gilt auch hier) und `../bec_u15_auswertung/` als
Vorbild/Quelle der übernommenen Module.

## Status (2026-09-18, Phase 1 abgeschlossen)

- Projekt angelegt, `.venv` mit den Kern-Dependencies installiert, `u17_int.db` per `schema.sql`
  angelegt.
- Wiederverwendbare, schema-unabhängige Module 1:1 (bzw. mit kleinen Anpassungen) aus
  `bec_u15_auswertung` übernommen -- siehe "Übernommene Module" unten.
- **Phase 1 (`load_turnierkatalog.py`) erledigt**: beide Turnierkatalog-Excel-Dateien
  (`_TOURNAMENT_DATA/BEC-U17-Circuit/*.xlsx`) in die `turnier`-Tabelle geladen -- 48 Zeilen (29
  aus 2025, 19 aus 2026), alle mit gebauter URL (`tournament_code` bei keiner Zeile leer/NULL).
  Tier-Verteilung: 10× `U17 GP`, 15× `U17 IC`, 23× `U17 IS`. UPSERT auf `tournament_id`,
  verifiziert idempotent (zweiter Lauf bleibt bei 48 Zeilen). Keine doppelten `TournamentID`
  über beide Dateien hinweg.
- Noch **nicht** begonnen: Phase 2 (Scraping). Kein einziges Turnier bisher gescraped, `player`/
  `matches`/`turnier_ergebnisse` sind noch leer.

## Datenbasis

48 Turniere insgesamt: `U19_RankingTournaments_2025_ausschliesslich-BEC-U17-Differenzierung.xlsx`
(29 Turniere) + `..._2026_...xlsx` (19 Turniere), beide unter
`_TOURNAMENT_DATA/BEC-U17-Circuit/`. Alle mit `Grading="BEC U17 Circuit"`, differenziert nach
`BEC17type` (Tier: IC/IS/GP). Spalten `TournamentID`/`TournamentCode` (GUID) erlauben den
direkten URL-Bau (`https://www.tournamentsoftware.com/tournament/{TournamentCode}`) -- anders als
beim U15-Vorbild, das URLs manuell in einer `tournament-urls.csv` sammeln musste.

**Entscheidung (User, 2026-09-18): `UseInRanking=False`-Zeilen (5 von 48, verifiziert nach dem
Laden) werden trotzdem mit aufgenommen.** Dieses Flag stammt aus der BRAIN-DBV-Pipeline und
bezieht sich auf die DBV-U19-Ranglisten-Eligibilität, nicht auf die Vollständigkeit des
BEC-Circuits selbst.

## Architekturentscheidungen (User-bestätigt, 2026-09-18)

- **Disziplinen: Einzel + Doppel + Mixed** (nicht nur Einzel wie beim U15-Vorbild). Disziplin-Codes
  international/englisch, da die BEC-Circuit-Turniersoftware englischsprachig ist: `BS`=Boys
  Singles, `GS`=Girls Singles, `BD`=Boys Doubles, `GD`=Girls Doubles, `XD`=Mixed Doubles.
- **Punktetabelle: vorerst flach**, wie beim U15-Vorbild (`punktetabelle.bec17type` bleibt NULL für
  alle Zeilen), trotz der expliziten Tier-Differenzierung (`BEC17type`: IC/IS/GP) in den
  Quelldateien. Die Spalte `bec17type` existiert im Schema bereits jetzt (nullable), damit eine
  spätere Umstellung auf tier-abhängige Werte kein Schema-Redesign braucht -- nur zusätzliche
  Zeilen mit gesetztem `bec17type`. **Offen**: woher die tier-abhängigen Werte kommen (offizielle
  BEC-Quelle nötig), wurde bewusst vertagt.
- **Best-of-N für die Punkte-Rangliste**: noch nicht festgelegt, U15-Vorbild nutzt Best-of-3
  (`aktualisiere_rangliste.update_rangliste_best_of_three`). Vor Phase 3 entscheiden.
- **DB normalisiert von Anfang an** (kein Wide-Column-Muster wie `player.bfib`/`bfib_punkte` im
  U15-Vorbild) -- siehe `schema.sql`. Neue `turnier`-Stammtabelle (Jahr/KW/Land/Tier/URL/
  TournamentID/TournamentCode), da 48 Einzelturniere über 2 Jahre eine echte
  Turnier-Metadatentabelle brauchen, nicht nur eine Kurz-Abkürzung wie beim U15-Vorbild.
  `matches`/`turnier_ergebnisse` unterstützen Doppelpaare (`*_spieler1_id`/`*_spieler2_id`).

## Modul-Herkunft: von "U15-Module übernehmen" zu eigenständiger API-Pipeline (Stand 2026-09-18)

**Der in Phase 0 übernommene Selenium/tournamentsoftware.com-Modulsatz aus `bec_u15_auswertung`
(`player_scraper.py`, `draw_scraper.py`, `match_scraper.py`, `cookie_handler.py`,
`cookie_and_consent_handler.py`, `csv_handler.py`, `fuzzy_utils.py`, `memory_manager.py`,
`player_in_list.py`, `club_manager.py`, `db_utils.py`) wurde wieder ENTFERNT** -- siehe
"BEC-Datenhub-API" unten für den Grund: die tatsächliche Datenquelle ist seit der
Cloudflare-Blocker-Recherche eine komplett andere (badmintoneurope.com statt
tournamentsoftware.com), erreichbar per einfachem `requests`, ohne Browser, ohne Login, ohne
Fuzzy-Name-Matching. Der U15-Modulsatz bleibt als Vorlage nur in `../bec_u15_auswertung/`
einsehbar, falls er für eine spätere, andere Datenquelle doch noch gebraucht wird.

## DB-Schema

Siehe `schema.sql` (per `create_db.py` idempotent nach `u17_int.db` angewendet). Tabellen:
`turnier`, `player`, `matches`, `turnier_ergebnisse`, `punktetabelle`, `rangliste`. (`names`/
`clubs` aus der ursprünglichen Phase-0-Planung entfernt -- nicht mehr nötig, siehe unten.)

## Phasenplan

- **Phase 0 (erledigt)**: Projekt-Setup, Module übernommen, Schema angelegt, Quelldaten kopiert.
- **Phase 1 (erledigt)**: Turnierkatalog aus den beiden Excel-Dateien in `turnier` geladen
  (`load_turnierkatalog.py`), URLs gebaut.
- **Phase 2 (BLOCKIERT, 2026-09-18)**: Scraping (Spieler, Draws inkl. Doppel/Mixed, Matches) pro
  Turnier, resumable; Fuzzy-Matching + `memory_manager` für Namenskonflikte. **Fundamentaler
  Blocker gefunden, bevor auch nur ein Turnier gescraped wurde**: alle 48 von 48 Turnier-URLs
  (`https://www.tournamentsoftware.com/tournament/{code}`) leiten beim Aufruf auf eine
  Login-Seite von `bwf.tournamentsoftware.com` um (`.../user/login?ReturnUrl=...`) --
  verifiziert per `tools/debug_check_redirects.py`, Ergebnis in
  `tools/_debug_redirect_check_all48.txt`. Anders als beim U15-Vorbild (öffentliche
  National-Verband-Instanzen von tournamentsoftware.com) scheinen die BEC-U17-Circuit-Turniere
  ausschließlich über das zugangsbeschränkte BWF-Portal einsehbar zu sein -- kein einziges der
  48 Turniere war ohne Login erreichbar. **Kein Bypass-Versuch unternommen** (kein
  Credential-Guessing, kein Umgehen der Zugriffssperre) -- Entscheidung liegt beim User: siehe
  Session-Verlauf für die zur Diskussion gestellten Optionen (legitime BWF-Zugangsdaten falls
  vorhanden, öffentliche Spiegelung auf nationalen Verbandsseiten pruefen, alternative
  BEC/BWF-Datenquelle, oder Scope-Reduktion). Noch kein einziges Turnier gescraped, `player`/
  `matches`/`turnier_ergebnisse` weiterhin leer. `draw_scraper.py`/`match_scraper.py` haben ihre
  Phase-0-TODO-Kommentare (Doppel/Mixed-Erweiterung) noch unangetastet, da eine funktionale
  Erweiterung vor Klärung des Zugriffsproblems keinen Sinn ergibt.

  **User-Hinweis (2026-09-18): `badmintoneurope.com` als öffentliche Alternative.** Muster
  `https://badmintoneurope.com/web/corporate/tournament?tournament_code={code}` (gleiches
  `TournamentCode`-GUID wie im Excel-Katalog) verlangt **kein** Login -- Fortschritt gegenüber
  dem BWF-Portal. Recherche per `tools/debug_research_bec_site.py` +
  `tools/debug_bec_network.py`: die Seite ist eine React/Liferay-SPA
  (`com-stellis-one-bec-sportdata-web`-Komponenten `TournamentDraws`/`TournamentMatches`/
  `TournamentEntries`/`TournamentHistory` im Page-Source sichtbar -- die Daten wären also
  grundsätzlich da), aber **Cloudflare Turnstile (Bot-Erkennung) greift vor dem eigentlichen
  Daten-Request**: Netzwerk-Log (CDP Performance-Log) zeigt einen
  `cdn-cgi/challenge-platform/.../chl_page`-Request unmittelbar nach dem Seitenaufruf --
  Headless-Selenium bekommt eine Challenge-Seite statt echtem Content, keine einzige
  API-/JSON-Anfrage für Turnierdaten feuert. Kein Umgehungsversuch unternommen (kein
  Fingerprint-Spoofing, kein Turnstile-Bypass) -- das wäre eine bewusste
  Bot-Erkennungs-Umgehung und braucht explizite User-Entscheidung. Zur Diskussion stehende
  Optionen: (a) nicht-headless/"menschlicher" Selenium-Lauf testen (nicht garantiert, Cloudflare
  erkennt oft trotzdem `navigator.webdriver`), (b) Claude-in-Chrome nutzen (steuert den
  echten Chrome-Browser/Profil des Users statt einer frischen automatisierten Instanz --
  plausibel unauffälliger gegenüber Cloudflare, aber pro Turnier interaktiv/langsamer), (c)
  halbmanueller Ansatz analog dem "JOT"-Sonderfall im U15-Vorbild, (d) weiter nach einer
  dritten, unauffälligeren öffentlichen Quelle suchen.

  **Ergebnis (User-Test, 2026-09-18): Claude-in-Chrome (echter Chrome-Browser des Users) kommt
  an Cloudflare vorbei, automatisiertes Python-Selenium NICHT** (auch nicht-headless getestet --
  `tools/debug_bec_nonheadless.py`, gleiches Blockmuster wie headless: nur Navigations-Chrome,
  keine Turnierdaten, kein Bypass-Versuch über Fingerprint-Spoofing unternommen). Per
  Claude-in-Chrome erfolgreich abgerufen (Turnier "Spanish U17 Open 2025",
  `tournament_code=E6A03CB2-...`): die Seite nutzt URL-Query-Param `tournament_tab`
  (`overview`/`entries`/`matches`, vermutlich auch `draws`/`history`) statt Klick-Navigation --
  direkte URL-Navigation reicht, kein Tab-Klicken nötig. **`tournament_tab=matches` liefert für
  ALLE 5 Disziplinen (MS/WS/MD/WD/XD U17) in einer Seite: Runde, Match-Nr., Dauer, beide
  Namen je Seite (bei MD/WD/XD bereits zwei Namen = Doppelpaarung), Satzergebnisse, Seed.**
  `tournament_tab=entries` liefert die volle Teilnehmerliste mit Setzung/Main-Draw-Reserve-
  Withdrawn-Status (bisher nur MS-U17 ohne weiteren Klick getestet -- andere Disziplinen
  vermutlich über ein weiteres Sub-Tab, noch zu klären). `tournament_tab=overview` zeigt zusätzlich
  eine `WINNERS`-Sektion mit Platzierung + **`POINTS`-Wert** je Disziplin (z.B. Platz 1: 640,
  Platz 2: 535, Platz 3/4: 440) -- könnte eine bereits von BEC selbst gepflegte Punktetabelle
  sein, relevant für die offene "Punktetabelle tier-abhängig"-Frage aus Phase-0/CLAUDE.md.
  **Datenqualität insgesamt deutlich besser als ursprünglich für tournamentsoftware.com
  erwartet** (echte Satzergebnisse statt nur Endplatzierung, saubere Doppel-Paar-Struktur ohne
  Namens-Split-Heuristik nötig). Ursprünglich als offene Architekturfrage notiert (Claude-in-Chrome
  interaktiv vs. Batch) -- **durch den folgenden Fund hinfällig geworden**.

  **DURCHBRUCH (2026-09-18): eigenständige JSON-API `bec-dh-prod.badmintoneurope.com` gefunden,
  per normalem `requests.get()` erreichbar -- kein Browser, kein Cloudflare-Block, kein Login.**
  Per `read_network_requests` (Claude-in-Chrome) entdeckt: die React-App auf
  `badmintoneurope.com` selbst holt ihre Daten von einem separaten Backend-Host, der (anders als
  die Hauptseite) NICHT hinter Cloudflare Turnstile hängt -- verifiziert per einfachem
  Python-`requests`-Aufruf ohne jede Browser-Automatisierung, an zwei unabhängigen Turnieren
  reproduziert (`tools/debug_bec_*` durch die eigentliche Pipeline `fetch_bec_data.py` ersetzt).
  `robots.txt` von badmintoneurope.com: `Disallow:` (leer, alles erlaubt); die API-Subdomain hat
  gar keine robots.txt (404 -- reiner JSON-Endpunkt, kein crawlbares Webangebot).

  **Endpunkte** (Basis `https://bec-dh-prod.badmintoneurope.com`, Pfad-Parameter = `tournament_code`
  = dieselbe GUID wie in unserer `turnier`-Tabelle):
  - `GET /tournament/{code}` -- Metadaten (`name`, `startDate`, `endDate`, `venueCountry`, ...).
    `level` ist nur die Altersklasse (`"u17"`), NICHT der Tier (IC/IS/GP) -- Tier steht als
    Freitext in `extraData.descriptionHtml` (z.B. `"U17 International Challenge"`).
  - `GET /tournament/{code}/events` -- die 5 Disziplinen dieses Turniers mit BEC-eigenen Codes
    (`eventLabel` z.B. `"MS U17"`).
  - `GET /tournament/{code}/matches/{yyyy-mm-dd}` -- **Kernendpunkt**: Liste von
    Ort/Platz-Blöcken, je mit `matches[]`. Jedes Match: `id` (stabil, fürs idempotente Upsert),
    `eventLabel`, `roundName`, `matchState` (`"F"` = finished/gespielt, andere Werte = nicht
    gespielt -- nur `"F"` mit gesetztem `winner` wird importiert), `winner` (1 oder 2),
    `games[]` (`team1Result`/`team2Result` je Satz), `team1`/`team2` (je `player1`/`player2` --
    `player2` NULL bei Einzel, gesetzt bei Doppel/Mixed). Jeder `player`-Eintrag hat eine
    **stabile `playerId`** (BEC-interne Athleten-ID) + `memberId` (Verbands-Mitgliedsnummer) +
    `firstName`/`lastName`/`countryCode`/`genderId`.
  - `GET /tournament/{code}/draw/{eventCode}` -- volle Turnierbaum-Struktur (233 KB für ein
    64er-Feld) inkl. `eliminationDrawColumnDTOS` -- **noch nicht genutzt**, enthält vermutlich
    Setzliste/Platzierung, relevant für Phase 3 falls `matches` allein nicht reicht.
  - `GET /tournament/{code}/winners` existiert NICHT als eigener Endpunkt (404) -- die
    `WINNERS`-Sektion der Webseite (Platz + `POINTS`-Wert) wird vermutlich aus `draw/{eventCode}`
    abgeleitet, noch nicht nachvollzogen.

  **Größter Architekturgewinn: `playerId` macht die gesamte U15-Fuzzy-Matching-Infrastruktur
  überflüssig.** Das U15-Projekt musste Namen über verschiedene tournamentsoftware.com-Instanzen
  hinweg per `fuzzy_utils`/`memory_manager`/interaktiver Konfliktauflösung zusammenführen, weil es
  keine turnierübergreifende Spieler-ID gab. Die BEC-API liefert dieselbe `playerId` konsistent
  über alle Turniere -- `spieler.bec_player_id UNIQUE` (siehe `schema.sql`) reicht als
  Upsert-Schlüssel, keine Namens-Heuristik nötig. Deshalb wurden `fuzzy_utils.py`,
  `memory_manager.py`, `player_in_list.py`, `club_manager.py`, `db_utils.py` sowie der komplette
  Selenium/Cookie-Modulsatz wieder entfernt (siehe "Modul-Herkunft"-Abschnitt oben).

  **`fetch_bec_data.py`** (ersetzt die ursprünglich für Phase 2 geplanten Selenium-Skripte):
  pro `turnier`-Zeile Metadaten abrufen (für den Datumsbereich), dann `/matches/{date}` für jeden
  Turniertag, Spieler + Matches per `bec_player_id`/`bec_match_id` upserten,
  `turnier.scraped_at` setzen (resumable via `WHERE scraped_at IS NULL`, `--no-resume` erzwingt
  Neuabruf). Höflichkeits-Delay `REQUEST_DELAY_SECONDS = 0.4` zwischen Requests, eigener
  `User-Agent`-Header. Getestet an den ersten 3 Turnieren (`--limit 3`): 719 Matches, 377 Spieler,
  alle 5 Disziplinen vertreten, Einzel/Doppel korrekt unterschieden (Doppel: 4 distinkte
  `spieler_id`, Einzel: `*_spieler2_id` NULL) -- siehe Session-Verlauf für Stichprobenwerte.

  **BEC-eventLabel-Präfix ≠ unser Disziplin-Code**: BEC nutzt für U17 die Erwachsenen-Kürzel
  `MS`/`WS`/`MD`/`WD`/`XD` (Männer/Frauen-Konvention) statt der in Phase 0 für dieses Projekt
  festgelegten Jugend-Kürzel `BS`/`GS`/`BD`/`GD`/`XD` (Boys/Girls) -- `EVENT_LABEL_TO_DISZIPLIN`
  in `fetch_bec_data.py` mappt explizit, keine Annahme "Label == Code".

  **Nicht mehr offen: BWF-Login-Blocker und Cloudflare-Blocker sind gegenstandslos** -- die
  finale Pipeline berührt weder `tournamentsoftware.com` noch die
  `badmintoneurope.com`-Hauptseite selbst, nur die unabhängige Datenhub-API.

- **Entscheidung (User, 2026-09-18): Turnierstärke wird NICHT aus dem BEC-Tier-Label (IC/IS/GP)
  oder einer fixen Punktetabelle abgeleitet, sondern empirisch aus der tatsächlichen Stärke der
  Teilnehmer berechnet -- analog `bec_u15_auswertung/compute_elo_strength.py`.** Die
  `WINNERS`-`POINTS`-Werte von der Webseite (Platz 1: 640, Platz 2: 535, ...) sind damit **nicht**
  die Zielgröße für die Turnierstärke, allenfalls späterer Vergleichswert. Das relativiert die
  ursprüngliche Phase-0-Frage nach einer tier-abhängigen Punktetabelle: die Punkte-Rangliste
  (Phase 3) bleibt ein separates, einfacheres Modell (flache Punktetabelle wie beim U15-Vorbild),
  die eigentliche Turnierstärke-Aussage liefert die Elo-Komponente (Phase 4), nicht Phase 3.
- **Phase 3**: Punkte-Rangliste (Punktetabelle anwenden, Best-of-N je Disziplin aggregieren,
  Export).
- **Phase 4**: Elo-Rangliste + Turnierstärke (analog `compute_elo_strength.py`, je Disziplin/
  Geschlecht) -- **das eigentliche Kernziel des Projekts** (siehe Entscheidung oben), nicht nur
  Nice-to-have neben der Punkte-Rangliste.
- **Phase 5** (später, optional): tier-abhängige Punktetabelle nachrüsten, Abgleich mit
  DBV-Daten für deutsche Teilnehmer (`player.german_spieler_id`, analog
  `RESULTS_AUSLAENDISCHE_TURNIERE/` im BRAIN-Projekt).

## Working conventions

Übernommen aus `../CLAUDE.md` (übergeordnetes Domänenmodell-Projekt): PowerShell-Aufgaben >10
Zeilen als `.ps1`-Datei ausführen, Python-Analysen >5 Zeilen als `tools/debug_*.py` statt langer
Inline-Kommandos.
