"""Rückanonymisierung der Claude-Antwort.

Toleriert verstümmelte Platzhalter ([Vorname 1], [VORNAME-1], [nachname_2_b])
und meldet jede Abweichung im Prüfbericht. Unbekannte Platzhalter bleiben
sichtbar stehen und machen den Bericht rot – nichts wird geraten.
"""

from __future__ import annotations

import re

from ..platzhalter.ersetzen import PLATZHALTER_LOSE_RE, PLATZHALTER_RE, platzhalter_name, typ_normalisieren
from ..typen import TYPEN, Pruefbericht

_TYP_ALIASE = {"NAME": None, "STRASSE": "STRASSE", "STRAE": "STRASSE", "GEBURTSTAG": "GEBURTSDATUM",
               "POSTLEITZAHL": "PLZ", "STEUERIDENTIFIKATIONSNUMMER": "STEUERID", "MAIL": "EMAIL"}
_OHNE_KLAMMERN_RE = re.compile(r"(?<![\[\w])(?P<typ>" + "|".join(TYPEN) + r")_(?P<nr>\d+)(?:_(?P<var>[A-Z]))?(?![\w\]])")


def einsetzen(antwort: str, zuordnung: dict[str, str]) -> tuple[str, Pruefbericht]:
    bericht = Pruefbericht()
    unbekannt: list[str] = []
    korrigiert: list[str] = []

    def ersetze(m: re.Match) -> str:
        roh = m.group()
        typ = typ_normalisieren(m.group("typ"))
        typ = _TYP_ALIASE.get(typ, typ) or typ
        if typ not in TYPEN and typ not in {"NAME", "PERSON", "ANSCHRIFT", "ADRESSE"}:
            return roh  # z. B. "[Anlage 1]" – kein Platzhalter
        var = (m.group("var") or "").upper()
        kanonisch = platzhalter_name(typ, int(m.group("nr")), var)
        if kanonisch in zuordnung:
            if roh != kanonisch:
                korrigiert.append(f"{roh} → {kanonisch}")
            return zuordnung[kanonisch]
        grund = platzhalter_name(typ, int(m.group("nr")))
        if var and grund in zuordnung:
            bericht.warnung("Platzhalter", f"{roh}: Schreibvariante unbekannt, Grundform {grund} eingesetzt.")
            return zuordnung[grund]
        unbekannt.append(roh)
        return roh

    text = PLATZHALTER_LOSE_RE.sub(ersetze, antwort)

    for m in _OHNE_KLAMMERN_RE.finditer(text):
        kanonisch = platzhalter_name(m.group("typ"), int(m.group("nr")), m.group("var") or "")
        if kanonisch in zuordnung:
            bericht.warnung("Platzhalter", f"{m.group()} ohne eckige Klammern gefunden – nicht ersetzt, bitte prüfen.")

    if korrigiert:
        bericht.info("Platzhalter", "Abweichende Schreibweise toleriert: " + ", ".join(sorted(set(korrigiert))))
    for ph in sorted(set(unbekannt)):
        bericht.fehler("Platzhalter", f"{ph} ist im Tresor unbekannt (von Claude erfunden?) – bleibt stehen, bitte von Hand ergänzen.")
    rest = [m.group() for m in PLATZHALTER_RE.finditer(text) if m.group() not in unbekannt]
    if rest:
        bericht.fehler("Rückanonymisierung", "Nicht ersetzte Platzhalter: " + ", ".join(sorted(set(rest))))
    return text, bericht
