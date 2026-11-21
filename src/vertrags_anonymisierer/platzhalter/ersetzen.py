"""Kern: Werte erkennen, Platzhalter vergeben, Text anonymisieren.

Grundsatz für die fehlerfreie Rückanonymisierung: Jeder Platzhalter steht für
genau EINE exakte Schreibweise. Ersetzt wird positionsgenau; alles außerhalb
der Fundstellen bleibt Zeichen für Zeichen erhalten. Damit gilt
    einsetzen(anonymisiere(text)) == text
und das prüft der Harness vor jedem Versand.
"""

from __future__ import annotations

import re
from dataclasses import asdict

from ..erkennung import ner, regeln
from ..erkennung.zuordnung import EmbeddingBackend, Gruppe, gruppiere
from ..typen import TYPEN, WERT_TYPEN, Eintrag, Fund, Kandidat

PLATZHALTER_RE = re.compile(r"\[(?P<typ>[A-Z]+)_(?P<nr>\d+)(?:_(?P<var>[A-Z]))?\]")
# Tolerant: [Vorname 1], [VORNAME-1], [ nachname_2_b ], [STRAßE_1] ...
PLATZHALTER_LOSE_RE = re.compile(
    r"\[\s*(?P<typ>[A-Za-zÄÖÜäöüß]+(?:[-_ ]?ID)?)[\s_\-]*(?P<nr>\d+)(?:[\s_\-]*(?P<var>[A-Za-z]))?\s*\]"
)

_PRIO = {"manuell": 0, "regel": 1, "variante": 2, "wertsuche": 2, "ner": 3}


class PlatzhalterKollision(ValueError):
    """Der Originaltext enthält bereits etwas, das wie ein Platzhalter aussieht."""


def typ_normalisieren(roh: str) -> str:
    t = roh.upper().replace("ß", "SS").replace("Ä", "AE").replace("Ö", "OE").replace("Ü", "UE")
    t = re.sub(r"[^A-Z]", "", t)
    return t


def platzhalter_name(typ: str, nummer: int, variante: str = "") -> str:
    return f"[{typ}_{nummer}_{variante}]" if variante else f"[{typ}_{nummer}]"


def _wert_muster(wert: str) -> re.Pattern:
    # Wortgrenzen; ein Genitiv-s bzw. Apostroph darf folgen und bleibt stehen.
    return re.compile(rf"(?<![\w]){re.escape(wert)}(?=(?:s|')?(?![\w]))")


def _varianten(typ: str, wert: str) -> list[str]:
    erg = []
    if typ in {"VORNAME", "NACHNAME", "FIRMA", "ORT", "GEMARKUNG", "STRASSE"}:
        erg.append(wert.upper())
        trans = wert
        for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("Ä", "Ae"), ("Ö", "Oe"), ("Ü", "Ue"), ("ß", "ss")):
            trans = trans.replace(a, b)
        erg.append(trans)
        erg.append(trans.upper())
    if typ == "VORNAME":
        erg.extend(t for t in re.split(r"[  ]+", wert) if len(t) >= 3 and t != wert)
    if typ == "IBAN":
        erg.append(wert.replace(" ", ""))
    return [v for v in dict.fromkeys(erg) if v and v != wert]


def ueberlappungen_aufloesen(funde: list[Fund]) -> list[Fund]:
    """Längere Fundstellen gewinnen, bei Gleichstand die verlässlichere Quelle."""
    sortiert = sorted(funde, key=lambda f: (-(f.ende - f.start), _PRIO.get(f.quelle, 9), f.start))
    belegt: list[tuple[int, int]] = []
    ergebnis: list[Fund] = []
    for f in sortiert:
        if any(f.start < e and s < f.ende for s, e in belegt):
            continue
        belegt.append((f.start, f.ende))
        ergebnis.append(f)
    return sorted(ergebnis, key=lambda f: f.start)


class Anonymisierer:
    """Eine Sitzung = ein Vorgang (Auftrag + Dokument teilen eine Zuordnung)."""

    def __init__(self, backend: EmbeddingBackend | None = None, *, ner_modell: str | None = None,
                 betraege: bool = False, schwelle: float = 0.9, aktive_typen: set[str] | None = None):
        self.backend = backend or EmbeddingBackend()
        self.ner_modell = ner_modell
        self.betraege = betraege
        self.schwelle = schwelle
        self.aktive_typen = aktive_typen or set(TYPEN)
        self.kandidaten: dict[tuple[str, str], Kandidat] = {}
        self.zuordnung: dict[str, Eintrag] = {}
        self._wert_zu_ph: dict[tuple[str, str], str] = {}
        self.gruppen: list[Gruppe] = []
        self._regelfunde: dict[str, list[Fund]] = {}

    # ---------- 1. Erkennen ----------
    def _grundfunde(self, text: str) -> list[Fund]:
        if text not in self._regelfunde:
            funde = regeln.erkenne(text, betraege=self.betraege)
            if self.ner_modell:
                funde += ner.erkenne(text, self.ner_modell)
            self._regelfunde[text] = [f for f in funde if f.typ in self.aktive_typen]
        return self._regelfunde[text]

    def analysiere(self, *texte: str) -> list[Kandidat]:
        for text in texte:
            self._pruefe_kollision(text)
            for f in self._grundfunde(text):
                self._kandidat(f.typ, f.wert, f.quelle, f.sicher)
        # Genitiv: "Schneiders" ist kein eigener Name, wenn "Schneider" bekannt ist.
        for typ, wert in [k for k in self.kandidaten if k[0] in {"NACHNAME", "VORNAME"}]:
            if wert.endswith("s") and (typ, wert[:-1]) in self.kandidaten:
                del self.kandidaten[(typ, wert)]
        # Schreibvarianten bekannter Werte (MÜLLER, Mueller) ebenfalls suchen.
        for (typ, wert), k in list(self.kandidaten.items()):
            for v in _varianten(typ, wert):
                if any(_wert_muster(v).search(t) for t in texte):
                    self._kandidat(typ, v, "variante", k.sicher)
        self._zaehlen(texte)
        # Varianten, die nur innerhalb längerer Funde stehen, nicht anzeigen.
        for key in [k for k, v in self.kandidaten.items() if v.quelle == "variante" and v.anzahl == 0]:
            del self.kandidaten[key]
        return self.kandidatenliste()

    def _kandidat(self, typ: str, wert: str, quelle: str, sicher: bool = True) -> Kandidat:
        key = (typ, wert)
        k = self.kandidaten.get(key)
        if k is None:
            k = self.kandidaten[key] = Kandidat(typ, wert, quelle, sicher)
        elif sicher and not k.sicher:
            k.sicher, k.quelle = True, quelle
        return k

    def ergaenze(self, typ: str, wert: str, *texte: str) -> Kandidat:
        """Manuell vom Menschen hinzugefügt – wird überall im Text gesucht."""
        typ = typ_normalisieren(typ)
        if typ not in TYPEN:
            raise ValueError(f"Unbekannter Typ {typ}")
        wert = wert.strip()
        if not wert:
            raise ValueError("Leerer Wert")
        k = self._kandidat(typ, wert, "manuell", True)
        k.quelle, k.aktiv = "manuell", True
        if texte:
            self._zaehlen(texte)
        return k

    def setze_aktiv(self, typ: str, wert: str, aktiv: bool) -> None:
        self.kandidaten[(typ, wert)].aktiv = aktiv

    def kandidatenliste(self) -> list[Kandidat]:
        reihenfolge = list(TYPEN)
        return sorted(self.kandidaten.values(), key=lambda k: (reihenfolge.index(k.typ), k.wert))

    def _zaehlen(self, texte) -> None:
        for k in self.kandidaten.values():
            k.anzahl = 0
        for text in texte:
            for f in self.funde(text, nur_aktiv=False):
                k = self.kandidaten.get((f.typ, f.wert))
                if k:
                    k.anzahl += 1

    # ---------- 2. Fundstellen ----------
    def funde(self, text: str, nur_aktiv: bool = True) -> list[Fund]:
        aktiv = {key for key, k in self.kandidaten.items() if k.aktiv or not nur_aktiv}
        funde = [f for f in self._grundfunde(text) if (f.typ, f.wert) in aktiv]
        for (typ, wert) in aktiv:
            k = self.kandidaten[(typ, wert)]
            if typ in WERT_TYPEN or k.quelle in ("manuell", "variante"):
                for m in _wert_muster(wert).finditer(text):
                    funde.append(Fund(m.start(), m.end(), typ, wert, "manuell" if k.quelle == "manuell" else "wertsuche"))
        return ueberlappungen_aufloesen(funde)

    # ---------- 3. Platzhalter vergeben ----------
    def baue_zuordnung(self, *texte: str) -> dict[str, Eintrag]:
        """Vergibt Nummern in Reihenfolge des ersten Auftretens über alle Texte."""
        reihenfolge: list[tuple[str, str]] = []
        for text in texte:
            for f in self.funde(text):
                if (f.typ, f.wert) not in reihenfolge:
                    reihenfolge.append((f.typ, f.wert))
        self.gruppen = gruppiere(reihenfolge, self.backend, self.schwelle)
        self.zuordnung.clear()
        self._wert_zu_ph.clear()
        zaehler: dict[str, int] = {}
        for g in self.gruppen:
            zaehler[g.typ] = zaehler.get(g.typ, 0) + 1
            for i, wert in enumerate(g.werte):
                variante = "" if i == 0 else chr(ord("A") + i)  # B, C, ...
                ph = platzhalter_name(g.typ, zaehler[g.typ], variante)
                self.zuordnung[ph] = Eintrag(ph, g.typ, zaehler[g.typ], variante, wert)
                self._wert_zu_ph[(g.typ, wert)] = ph
        return self.zuordnung

    # ---------- 4. Anonymisieren ----------
    def _pruefe_kollision(self, text: str) -> None:
        m = PLATZHALTER_LOSE_RE.search(text)
        if m:
            raise PlatzhalterKollision(
                f"Der Text enthält bereits die Zeichenfolge {m.group()!r}, die wie ein Platzhalter aussieht. "
                "Eine eindeutige Rückanonymisierung wäre nicht gewährleistet – bitte im Original ändern."
            )

    def anonymisiere(self, text: str) -> str:
        self._pruefe_kollision(text)
        teile: list[str] = []
        pos = 0
        for f in self.funde(text):
            ph = self._wert_zu_ph.get((f.typ, f.wert))
            if ph is None:
                raise RuntimeError("baue_zuordnung() muss vor anonymisiere() mit allen Texten laufen.")
            teile.append(text[pos:f.start])
            teile.append(ph)
            pos = f.ende
        teile.append(text[pos:])
        return "".join(teile)

    def platzhalter_fuer(self, typ: str, wert: str) -> str | None:
        return self._wert_zu_ph.get((typ, wert))

    def zuordnung_als_liste(self) -> list[dict]:
        return [asdict(e) for e in self.zuordnung.values()]


def einsetzen_strikt(text: str, zuordnung: dict[str, str]) -> str:
    """Ersetzt nur exakt geschriebene Platzhalter (für den Round-Trip-Test)."""
    return PLATZHALTER_RE.sub(lambda m: zuordnung.get(m.group(), m.group()), text)
