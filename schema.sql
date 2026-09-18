-- Schema für u17_int.db (BEC-U17-Auswertung)
-- Normalisiert von Anfang an (im Unterschied zum U15-Vorbild, das anfangs mit
-- Wide-Columns je Turnierserie gearbeitet hat -- ungeeignet für 48 Einzelturniere).

CREATE TABLE IF NOT EXISTS turnier (
    turnier_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ranking_tournament_id   INTEGER,        -- RankingTournamentID aus der BRAIN-Excel (Referenz)
    tournament_id           INTEGER,        -- TournamentID (numerische tournamentsoftware.com-ID)
    tournament_code         VARCHAR(64),    -- TournamentCode (GUID, Basis der Scraping-URL)
    name                    VARCHAR(200) NOT NULL,
    jahr                    INTEGER NOT NULL,
    kw                      INTEGER,
    land                    VARCHAR(3),
    bec17type               VARCHAR(16),    -- z.B. 'U17 IC', 'U17 IS', 'U17 GP'
    grading                 VARCHAR(64),
    use_in_ranking          BOOLEAN,        -- Herkunfts-Flag aus der BRAIN-Excel, nicht das eigene Ranking-Kriterium
    url                     TEXT,
    quelle_excel            VARCHAR(200),
    scraped_at               TEXT,   -- gesetzt von fetch_bec_data.py (Matches)
    entries_scraped_at       TEXT,   -- gesetzt von fetch_bec_entries_winners.py (Entries + Winners)
    UNIQUE(tournament_id)
);

-- Spieler-Identitaet kommt direkt aus der BEC-API (bec_player_id, stabil und eindeutig ueber
-- alle Turniere hinweg) -- anders als beim U15-Vorbild braucht es deshalb KEIN Fuzzy-Name-
-- Matching/memory_manager-Interaktion und keine "names"-Variantentabelle (siehe CLAUDE.md,
-- "BEC-Datenhub-API"-Abschnitt).
CREATE TABLE IF NOT EXISTS player (
    spieler_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    bec_player_id         INTEGER UNIQUE,   -- BEC-eigene playerId, Quelle der Wahrheit
    bec_member_id          VARCHAR(16),      -- BEC-eigene memberId (Verbands-Mitgliedsnummer)
    german_spieler_id    VARCHAR(16),   -- Link zur DBV-SpielerID (BRAIN-Projekt) für deutsche Teilnehmer
    name                  VARCHAR(64),
    vorname               VARCHAR(64),
    geburtsjahr           INTEGER,
    gender                VARCHAR(1),
    nation                VARCHAR(3)
);

-- Disziplin-Codes (international, da BEC-Circuit-Turniersoftware englischsprachig ist):
-- BS=Boys Singles, GS=Girls Singles, BD=Boys Doubles, GD=Girls Doubles, XD=Mixed Doubles
-- (BEC-API selbst nutzt MS/WS/MD/WD/XD -- Mapping beim Import, siehe CLAUDE.md)
CREATE TABLE IF NOT EXISTS matches (
    match_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    bec_match_id         INTEGER UNIQUE,  -- BEC-eigene match.id, fuer idempotenten Import
    turnier_id          INTEGER NOT NULL,
    disziplin           VARCHAR(2) NOT NULL,
    runde                VARCHAR(16),
    heim_spieler1_id     INTEGER,
    heim_spieler2_id     INTEGER,   -- NULL bei Einzel, Doppelpartner bei BD/GD/XD
    gast_spieler1_id     INTEGER,
    gast_spieler2_id     INTEGER,   -- NULL bei Einzel, Doppelpartner bei BD/GD/XD
    ergebnis              VARCHAR(64),
    winner_seite          VARCHAR(4),  -- 'heim' oder 'gast'
    FOREIGN KEY (turnier_id) REFERENCES turnier(turnier_id),
    FOREIGN KEY (heim_spieler1_id) REFERENCES player(spieler_id),
    FOREIGN KEY (heim_spieler2_id) REFERENCES player(spieler_id),
    FOREIGN KEY (gast_spieler1_id) REFERENCES player(spieler_id),
    FOREIGN KEY (gast_spieler2_id) REFERENCES player(spieler_id)
);

-- Teilnehmerliste je Turnier/Disziplin, aus der ersten Draw-Runde der BEC-API abgeleitet
-- (enthaelt damit alle tatsaechlich im Hauptfeld ausgelosten Teilnehmer inkl. Freilose;
-- eine gesonderte Reserve-/Withdrawn-Liste liefert die API nicht, siehe CLAUDE.md).
CREATE TABLE IF NOT EXISTS entries (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    turnier_id      INTEGER NOT NULL,
    disziplin        VARCHAR(2) NOT NULL,
    spieler1_id      INTEGER NOT NULL,
    spieler2_id      INTEGER,   -- NULL bei Einzel, Partner bei BD/GD/XD
    seed              VARCHAR(8),
    FOREIGN KEY (turnier_id) REFERENCES turnier(turnier_id),
    FOREIGN KEY (spieler1_id) REFERENCES player(spieler_id),
    FOREIGN KEY (spieler2_id) REFERENCES player(spieler_id)
);

CREATE TABLE IF NOT EXISTS turnier_ergebnisse (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    turnier_id      INTEGER NOT NULL,
    disziplin        VARCHAR(2) NOT NULL,
    spieler1_id      INTEGER NOT NULL,
    spieler2_id      INTEGER,   -- NULL bei Einzel, Partner bei BD/GD/XD
    platzierung      INTEGER,
    punkte            INTEGER,
    FOREIGN KEY (turnier_id) REFERENCES turnier(turnier_id),
    FOREIGN KEY (spieler1_id) REFERENCES player(spieler_id),
    FOREIGN KEY (spieler2_id) REFERENCES player(spieler_id)
);

-- Punktetabelle: bec17type ist bewusst nullable/vorerst ungenutzt (siehe CLAUDE.md,
-- "Punktetabelle"-Entscheidung 2026-09-18) -- Start mit einer flachen, tier-unabhängigen
-- Tabelle wie beim U15-Vorbild (bec17type = NULL für alle Zeilen). Spalte existiert bereits
-- jetzt, damit eine spätere Umstellung auf tier-abhängige Werte kein Schema-Redesign braucht,
-- nur das Befüllen zusätzlicher Zeilen mit gesetztem bec17type.
CREATE TABLE IF NOT EXISTS punktetabelle (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    bec17type   VARCHAR(16),
    platz        INTEGER NOT NULL,
    punkte        INTEGER NOT NULL,
    UNIQUE(bec17type, platz)
);

CREATE TABLE IF NOT EXISTS rangliste (
    spieler_id          INTEGER NOT NULL,
    disziplin            VARCHAR(2) NOT NULL,
    punkte                INTEGER NOT NULL DEFAULT 0,
    anzahl_turniere       INTEGER DEFAULT 0,
    berechnungsdatum      TEXT DEFAULT (DATE('now')),
    PRIMARY KEY (spieler_id, disziplin),
    FOREIGN KEY (spieler_id) REFERENCES player(spieler_id)
);
