import os
import pandas as pd
from db_utils import connect_db

DB_FOLDER = "."
DB_FILE = "u17_int.db"


class ClubManager:

    def __init__(self, debug=False):
        self.db_path = os.path.join(DB_FOLDER, DB_FILE)
        self.conn = None
        self.cursor = None
        self.debug = debug

    # ---------------------------------
    # Context Manager
    # ---------------------------------
    def __enter__(self):
        self.conn, self.cursor = connect_db(self.db_path)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:

            # Bei normalem Ablauf → commit
            if exc_type is None:
                self.conn.commit()

            # Bei SystemExit → commit behalten
            elif exc_type is SystemExit:
                self.conn.commit()

            # Bei echten Fehlern → rollback
            else:
                self.conn.rollback()

            self.conn.close()

        # SystemExit nicht unterdrücken
        return False

    # ---------------------------------
    # ADD CLUB
    # ---------------------------------
    COUNTRY_MAP = {
        "belge": "BEL",
        "netherland": "NED",
        "switzerland": "SUI",
        "czechia": "CZE",
        "luxemburg": "LUX",
        "denmark": "DEN",
        "england": "ENG",
        "germany": "GER",
    }


    def add(self, club_name: str, abbreviation: str, year: int, country: str = None):

        if not club_name or not abbreviation or year is None:
            raise ValueError("club_name, abbreviation und year sind Pflichtfelder!")

        if not isinstance(year, int):
            raise ValueError("year muss INTEGER sein!")

        if country:
            country = country.upper()
            if len(country) != 3:
                raise ValueError("country muss 3-stellig sein (ISO-Code)")

        # Automatische Erkennung falls kein country übergeben
        if not country:
            country = self._detect_country_from_name(club_name)

        # Existierenden Datensatz prüfen
        self.cursor.execute(
            "SELECT club_id, country FROM clubs WHERE club_name = ?",
            (club_name,)
        )
        existing = self.cursor.fetchone()

        # --------------------------------------------
        # CLUB EXISTIERT BEREITS
        # --------------------------------------------
        if existing:
            club_id, db_country = existing

            # Fall: kein neues country übergeben
            if not country:
                print(f"Bereits vorhanden: {club_name}")
                return

            # DB hat kein country → Update
            if not db_country:
                self.cursor.execute(
                    "UPDATE clubs SET country = ? WHERE club_id = ?",
                    (country, club_id)
                )
                print(f"Country ergänzt für {club_name}: {country}")
                return

            # Beide vorhanden
            if db_country == country:
                print(f"OK: {club_name} ({country}) bereits korrekt vorhanden.")
                return

            # Konfliktfall
            print(f"\nCountry-Konflikt bei '{club_name}'")
            print(f"DB:   {db_country}")
            print(f"Neu:  {country}")
            print("1 = DB behalten")
            print("2 = Neues übernehmen")
            print("3 = Abbrechen")

            while True:
                choice = input("Auswahl: ").strip()

                if choice == "1":
                    print("DB-Wert bleibt unverändert.")
                    return

                elif choice == "2":
                    self.cursor.execute(
                        "UPDATE clubs SET country = ? WHERE club_id = ?",
                        (country, club_id)
                    )
                    print(f"Country aktualisiert auf {country}")
                    return

                elif choice == "3":
                    print("Abbruch.")
                    return

                else:
                    print("Ungültige Eingabe.")

        # --------------------------------------------
        # NEUER CLUB
        # --------------------------------------------
        # --------------------------------------------
        # NEUER CLUB
        # --------------------------------------------
        if not country:
            country = self._ask_country(club_name)

            if country == "__SKIP__":
                if self.debug:
                    print(f"[SKIP] {club_name}")
                return

        # Insert
        self.cursor.execute("""
            INSERT INTO clubs (club_name, country, abbreviation, year)
            VALUES (?, ?, ?, ?)
        """, (club_name, country, abbreviation, year))

        if self.debug:
            print(f"[INSERT] {club_name} | {country} | {abbreviation} | {year}")

    def _detect_country_from_name(self, club_name: str):
        lower_name = club_name.lower()

        for key, value in self.COUNTRY_MAP.items():
            if key in lower_name:
                return value

        return None

    # ---------------------------------
    # GET COUNTRY
    # ---------------------------------
    def get_country(self, club_name: str) -> str:
        self.cursor.execute(
            "SELECT country FROM clubs WHERE club_name = ?",
            (club_name,)
        )
        result = self.cursor.fetchone()
        return result[0] if result and result[0] else ""

    # ---------------------------------
    # DUMP KONSOLE
    # ---------------------------------
    def dump_console(self):
        self.cursor.execute("SELECT * FROM clubs")
        rows = self.cursor.fetchall()

        print("\n---- CLUBS ----")
        for row in rows:
            print(row)

    # ---------------------------------
    # DUMP EXCEL
    # ---------------------------------
    def dump_excel(self, filename="clubs_export.xlsx"):
        df = pd.read_sql_query("SELECT * FROM clubs", self.conn)
        df.to_excel(filename, index=False)
        print(f"Export nach '{filename}' abgeschlossen.")

    # ---------------------------------
    # COUNTRY INPUT
    # ---------------------------------
    def _ask_country(self, club_name):

        while True:
            user_input = input(
                f"Land für '{club_name}' eingeben "
                "(0=Datensatz überspringen, 1=Programmende, "
                "oder 3-Buchstaben-Code): "
            ).strip()

            # 0 = gesamten Datensatz überspringen
            if user_input == "0":
                return "__SKIP__"

            # 1 = Programm beenden
            if user_input == "1":
                print("Programm wird beendet.")
                raise SystemExit(1)

            # gültiger 3-stelliger Code
            if len(user_input) == 3:
                return user_input.upper()

            print("Ungültige Eingabe.")