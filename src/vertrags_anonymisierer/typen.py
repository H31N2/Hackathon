"""Gemeinsame Datentypen.

Begriffe:
- Fund: eine Fundstelle im Text (Position, Typ, Wert).
- Eintrag: ein Platzhalter mit genau einem Originalwert (exakte Schreibweise).
- Gruppe: alle Einträge, die dieselbe Person/Sache meinen (gleiche Nummer),
  z. B. "Müller" -> [NACHNAME_1] und "MÜLLER" -> [NACHNAME_1_B].
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Reihenfolge = Anzeige-Reihenfolge in der Prüfansicht.
TYPEN: dict[str, str] = {
    "VORNAME": "Vorname",
    "NACHNAME": "Nachname",
    "FIRMA": "Firma",
    "STRASSE": "Straße und Hausnummer",
    "PLZ": "Postleitzahl",
    "ORT": "Ort",
    "GEBURTSDATUM": "Geburtsdatum",
    "IBAN": "IBAN",
    "BIC": "BIC",
    "EMAIL": "E-Mail",
    "TELEFON": "Telefon",
    "STEUERID": "Steuer-ID",
    "AUSWEIS": "Ausweisnummer",
    "URNR": "Urkundenrolle-Nr.",
    "GEMARKUNG": "Gemarkung / Grundbuchbezirk",
    "BLATT": "Grundbuchblatt",
    "FLURSTUECK": "Flurstück",
    "BETRAG": "Geldbetrag",
}

# Typen, deren Werte überall im Text ersetzt werden (Wertsuche).
# Bei allen anderen wird nur an der gefundenen Stelle ersetzt, damit z. B. die
# Blattnummer "12" nicht jedes "§ 12" mitnimmt.
WERT_TYPEN = {"VORNAME", "NACHNAME", "FIRMA", "STRASSE", "ORT", "GEMARKUNG", "EMAIL", "IBAN", "STEUERID", "AUSWEIS"}


@dataclass(frozen=True)
class Fund:
    start: int
    ende: int
    typ: str
    wert: str
    quelle: str = "regel"  # regel | ner | wertsuche | manuell
    sicher: bool = True


@dataclass
class Eintrag:
    platzhalter: str  # z. B. "[NACHNAME_1_B]"
    typ: str
    nummer: int
    variante: str  # "" für die Grundform, sonst "B", "C", ...
    wert: str


@dataclass
class Kandidat:
    """Ein erkannter Wert zur Prüfung durch den Menschen."""

    typ: str
    wert: str
    quelle: str
    sicher: bool
    anzahl: int = 0
    aktiv: bool = True


@dataclass
class Meldung:
    stufe: str  # FEHLER | WARNUNG | INFO
    pruefung: str
    text: str

    def __str__(self) -> str:
        return f"{self.stufe:7} {self.pruefung}: {self.text}"


@dataclass
class Pruefbericht:
    meldungen: list[Meldung] = field(default_factory=list)

    def fehler(self, pruefung: str, text: str) -> None:
        self.meldungen.append(Meldung("FEHLER", pruefung, text))

    def warnung(self, pruefung: str, text: str) -> None:
        self.meldungen.append(Meldung("WARNUNG", pruefung, text))

    def info(self, pruefung: str, text: str) -> None:
        self.meldungen.append(Meldung("INFO", pruefung, text))

    @property
    def gruen(self) -> bool:
        return not any(m.stufe == "FEHLER" for m in self.meldungen)

    def anhaengen(self, anderer: "Pruefbericht") -> None:
        self.meldungen.extend(anderer.meldungen)

    def als_dict(self) -> dict:
        return {
            "gruen": self.gruen,
            "meldungen": [m.__dict__ for m in self.meldungen],
        }
