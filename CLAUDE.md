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

## Übernommene Module (aus `../bec_u15_auswertung`)

Unverändert/generisch (kein Bezug zu U15-Schema oder -Disziplinen):
- `fuzzy_utils.py`, `memory_manager.py`, `player_in_list.py`, `db_utils.py`,
  `cookie_and_consent_handler.py`

Mit kleiner Anpassung übernommen:
- `club_manager.py` -- `DB_FILE` auf `u17_int.db` umgestellt, den BFIB-spezifischen
  Demo-/`__main__`-Block (Einlesen von `inscriptions.xlsx`) entfernt (galt nur fürs U15-Projekt,
  hier nicht anwendbar).
- `player_scraper.py` -- unverändert übernommen (gleiche Plattform tournamentsoftware.com).
- `draw_scraper.py`, `match_scraper.py` -- übernommen, aber mit `TODO`-Kommentar markiert: decken
  bisher nur Einzel (JE/ME-Pattern bzw. Ein-Spieler-pro-Seite) ab. Müssen in **Phase 2** um
  Doppel/Mixed erweitert werden (neue Tag-Pattern für BD/GD/XD in `draw_scraper.find_draw_links`;
  Zwei-Spieler-Namensauflösung je Seite in `match_scraper.py`, passend zum neuen
  `matches`-Schema).

Bewusst **nicht** übernommen (Phase 2/3-Arbeit, hängt eng am U15-spezifischen Schema/Workflow,
würde vor echter Anpassung nur totes/irreführendes Code-Gerüst im neuen Projekt hinterlassen):
`insert_players.py`, `insert_matches.py`, `insert_rank_and_points.py`, `ranking_table.py`,
`aktualisiere_rangliste.py`, `export_rankings_enhanced.py`, `name_clashes_handler.py`,
`clear_names_and_spieler_ids.py`, `compute_elo_strength.py`. Deren Kernlogik (siehe
Session-Notizen) ist als Vorlage weiterhin einsehbar in `../bec_u15_auswertung/`, wird aber erst
beim jeweiligen Phasen-Start neu geschrieben/angepasst.

## DB-Schema

Siehe `schema.sql` (per `create_db.py` idempotent nach `u17_int.db` angewendet). Tabellen:
`turnier`, `player`, `names`, `clubs`, `matches`, `turnier_ergebnisse`, `punktetabelle`,
`rangliste`.

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
  Namens-Split-Heuristik nötig). **Architektur-Konsequenz noch mit User zu klären**: eine
  vollautomatische Batch-Pipeline (wie ursprünglich für tournamentsoftware.com geplant) ist damit
  nicht ohne Weiteres möglich -- Scraping müsste über Claude-in-Chrome interaktiv/
  Turnier-für-Turnier laufen, nicht als unbeaufsichtigtes Python-Skript.
- **Phase 3**: Punkte-Rangliste (Punktetabelle anwenden, Best-of-N je Disziplin aggregieren,
  Export).
- **Phase 4**: Elo-Rangliste + Turnierstärke (analog `compute_elo_strength.py`, je Disziplin/
  Geschlecht).
- **Phase 5** (später, optional): tier-abhängige Punktetabelle nachrüsten, Abgleich mit
  DBV-Daten für deutsche Teilnehmer (`player.german_spieler_id`, analog
  `RESULTS_AUSLAENDISCHE_TURNIERE/` im BRAIN-Projekt).

## Working conventions

Übernommen aus `../CLAUDE.md` (übergeordnetes Domänenmodell-Projekt): PowerShell-Aufgaben >10
Zeilen als `.ps1`-Datei ausführen, Python-Analysen >5 Zeilen als `tools/debug_*.py` statt langer
Inline-Kommandos.
