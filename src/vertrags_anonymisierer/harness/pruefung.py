"""Harness: Leitplanken rund um den Claude-Aufruf.

Vor dem Versand (blockierend):
  1. Round-Trip: einsetzen(anonym) muss bytegleich das Original ergeben.
  2. Leck-Scan: kein Originalwert (auch GROSS, ae/ä, ohne Leerzeichen) darf im
     anonymisierten Text stehen.
  3. Nacherkennung: die Regeln laufen erneut über den anonymen Text; was dort
     noch gefunden wird, ist ein möglicher Rest (Warnung).

Nach der Antwort:
  4. Platzhalter-Abgleich (siehe rueck.deanonym.einsetzen).
  5. Vollständigkeit: welche Platzhalter des Auftrags fehlen in der Antwort.
  6. Neue Personendaten: Namen in der Antwort, die nicht aus dem Tresor stammen.
"""

from __future__ import annotations

import re

from ..erkennung import regeln
from ..platzhalter.ersetzen import PLATZHALTER_LOSE_RE, PLATZHALTER_RE, einsetzen_strikt
from ..rueck.deanonym import einsetzen
from ..typen import Pruefbericht

_NAMENSTYPEN = {"VORNAME", "NACHNAME", "FIRMA", "STRASSE", "ORT", "GEMARKUNG", "EMAIL", "IBAN", "STEUERID", "AUSWEIS"}


def _formen(wert: str) -> set[str]:
    formen = {wert, wert.upper()}
    trans = wert
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("Ä", "Ae"), ("Ö", "Oe"), ("Ü", "Ue"), ("ß", "ss")):
        trans = trans.replace(a, b)
    formen |= {trans, trans.upper()}
    if re.fullmatch(r"[\dA-Z ./-]+", wert):
        formen.add(re.sub(r"[ ./-]", "", wert))
    return formen


def round_trip(original: str, anonym: str, zuordnung: dict[str, str]) -> Pruefbericht:
    b = Pruefbericht()
    zurueck = einsetzen_strikt(anonym, zuordnung)
    if zurueck != original:
        pos = next((i for i, (x, y) in enumerate(zip(zurueck, original)) if x != y), min(len(zurueck), len(original)))
        b.fehler("Round-Trip", f"Rückanonymisierung weicht ab Zeichen {pos} vom Original ab – Versand gesperrt.")
    else:
        b.info("Round-Trip", f"bytegleich ({len(original)} Zeichen)")
    return b


def leck_scan(anonym: str, zuordnung: dict[str, str], typen: dict[str, str]) -> Pruefbericht:
    """typen: Platzhalter -> Typ."""
    b = Pruefbericht()
    ohne_ph = PLATZHALTER_RE.sub(" ", anonym)
    for ph, wert in zuordnung.items():
        typ = typen.get(ph, "")
        nur_ziffern = re.sub(r"\D", "", wert)
        if typ in _NAMENSTYPEN and len(wert) >= 3:
            for form in _formen(wert):
                if re.search(rf"(?<!\w){re.escape(form)}(?!\w)", ohne_ph):
                    b.fehler("Leck-Scan", f"{ph}: Originalwert steht noch im anonymisierten Text.")
                    break
            else:
                if len(wert) >= 4 and re.search(rf"(?<!\w){re.escape(wert)}(?!\w)", ohne_ph, re.I):
                    b.warnung("Leck-Scan", f"{ph}: Wert kommt in anderer Groß-/Kleinschreibung vor – bitte prüfen.")
        elif len(nur_ziffern) >= 5:
            for form in _formen(wert):
                if form in ohne_ph:
                    b.warnung("Leck-Scan", f"{ph}: Ziffernfolge kommt an anderer Stelle noch vor – bitte prüfen.")
                    break
    if b.gruen and not b.meldungen:
        b.info("Leck-Scan", f"{len(zuordnung)} Werte geprüft, kein Rest gefunden")
    return b


def nacherkennung(anonym: str) -> Pruefbericht:
    b = Pruefbericht()
    reste = {(f.typ, f.wert) for f in regeln.erkenne(anonym) if not PLATZHALTER_LOSE_RE.search(f.wert)}
    for typ, wert in sorted(reste):
        b.warnung("Nacherkennung", f"Möglicher Rest ({typ}): {wert!r} – in der Prüfansicht ergänzen oder bestätigen.")
    return b


def vor_versand(paare: list[tuple[str, str]], zuordnung: dict[str, str], typen: dict[str, str]) -> Pruefbericht:
    """paare: (original, anonym) für Auftrag und Dokument."""
    gesamt = Pruefbericht()
    for original, anonym in paare:
        gesamt.anhaengen(round_trip(original, anonym, zuordnung))
        gesamt.anhaengen(leck_scan(anonym, zuordnung, typen))
        gesamt.anhaengen(nacherkennung(anonym))
    return gesamt


def nach_antwort(anonym_eingang: str, antwort: str, zuordnung: dict[str, str]) -> tuple[str, Pruefbericht]:
    text, b = einsetzen(antwort, zuordnung)
    gesendet = {m.group() for m in PLATZHALTER_RE.finditer(anonym_eingang)}
    zurueck = {m.group() for m in PLATZHALTER_RE.finditer(antwort)}
    fehlend = sorted(gesendet - zurueck)
    personen = [p for p in fehlend if p.split("_")[0][1:] in {"VORNAME", "NACHNAME", "FIRMA"} and p.count("_") == 1]
    if fehlend:
        b.info("Vollständigkeit", f"{len(gesendet) - len(fehlend)} von {len(gesendet)} Platzhaltern in der Antwort verwendet.")
    if personen:
        b.info("Vollständigkeit", "Nicht mehr erwähnte Personen/Firmen: " + ", ".join(personen))
    # Namen, die Claude selbst eingeführt hat (z. B. Mustername), fallen hier auf.
    neu = {f.wert for f in regeln.erkenne(antwort) if f.typ in {"VORNAME", "NACHNAME", "FIRMA", "IBAN", "EMAIL"}
           and not PLATZHALTER_LOSE_RE.search(f.wert)}
    for wert in sorted(neu):
        b.warnung("Neue Daten", f"Claude nennt {wert!r}, das nicht aus dem Original stammt – bitte prüfen.")
    return text, b
