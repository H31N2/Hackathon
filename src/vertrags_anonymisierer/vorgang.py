"""Ablauf eines Vorgangs: laden -> erkennen -> prüfen -> anonymisieren -> Claude -> zurück.

Wird von Kommandozeile und Weboberfläche gleichermaßen benutzt.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .claude import auftrag as claude_auftrag
from .einlesen.dokument import docx_anonymisieren, text_laden
from .erkennung.zuordnung import backend_aus_konfig
from .harness import pruefung
from .platzhalter.ersetzen import Anonymisierer
from .platzhalter.tresor import Tresor, datenordner
from .rueck.ausgabe import speichern
from .typen import TYPEN, Kandidat, Pruefbericht


def protokollieren(eintrag: dict) -> None:
    """Protokoll ohne personenbezogene Daten (nur IDs, Zahlen, Prüfergebnisse)."""
    eintrag = {"zeit": datetime.now().isoformat(timespec="seconds"), **eintrag}
    with (datenordner() / "protokoll.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(eintrag, ensure_ascii=False) + "\n")


@dataclass
class Vorgang:
    konfig: dict
    auftrag: str = ""
    dokument: str = ""
    dateiname: str = ""
    quelle: Path | None = None
    anonymisierer: Anonymisierer = field(init=False)
    auftrag_anonym: str = ""
    dokument_anonym: str = ""
    vorgang_id: str = ""
    bericht_vorher: Pruefbericht = field(default_factory=Pruefbericht)
    antwort_anonym: str = ""
    ergebnis: str = ""
    bericht_nachher: Pruefbericht = field(default_factory=Pruefbericht)

    def __post_init__(self):
        e, emb = self.konfig["erkennung"], self.konfig["embedding"]
        self.anonymisierer = Anonymisierer(
            backend_aus_konfig(emb),
            ner_modell=e.get("ner_modell") or None,
            betraege=e.get("betraege", False),
            schwelle=emb.get("schwelle", 0.9),
            aktive_typen=set(TYPEN) - set(e.get("typen_aus", [])),
        )

    # 1. Laden und erkennen
    def laden(self, pfad: Path | None, auftrag: str) -> list[Kandidat]:
        self.auftrag = auftrag.strip()
        if pfad:
            self.quelle = Path(pfad)
            self.dateiname = self.quelle.name
            self.dokument = text_laden(self.quelle)
        return self.anonymisierer.analysiere(*self._texte())

    def _texte(self) -> list[str]:
        return [t for t in (self.auftrag, self.dokument) if t]

    def ergaenze(self, typ: str, wert: str) -> Kandidat:
        return self.anonymisierer.ergaenze(typ, wert, *self._texte())

    # 2. Anonymisieren + Prüfung vor Versand
    def vorbereiten(self) -> Pruefbericht:
        a = self.anonymisierer
        a.baue_zuordnung(*self._texte())
        self.auftrag_anonym = a.anonymisiere(self.auftrag) if self.auftrag else ""
        self.dokument_anonym = a.anonymisiere(self.dokument) if self.dokument else ""
        paare = [(o, n) for o, n in ((self.auftrag, self.auftrag_anonym), (self.dokument, self.dokument_anonym)) if o]
        self.bericht_vorher = pruefung.vor_versand(paare, self.zuordnung(), self.typen())
        for g in a.gruppen:
            if g.zusammengefuehrt_von:
                self.bericht_vorher.info("EmbeddingGemma", f"Als dieselbe Sache zugeordnet ({g.typ}): {len(g.werte)} Schreibweisen")
        return self.bericht_vorher

    def zuordnung(self) -> dict[str, str]:
        return {ph: e.wert for ph, e in self.anonymisierer.zuordnung.items()}

    def typen(self) -> dict[str, str]:
        return {ph: e.typ for ph, e in self.anonymisierer.zuordnung.items()}

    def im_tresor_ablegen(self, tresor: Tresor) -> str:
        self.vorgang_id = tresor.speichern(self.zuordnung(), self.dateiname or "Auftrag ohne Dokument",
                                           claude_auftrag.nachricht_bauen(self.auftrag_anonym, self.dokument_anonym))
        return self.vorgang_id

    # 3. Claude
    def an_claude(self, client=None) -> str:
        if not self.bericht_vorher.gruen:
            raise RuntimeError("Prüfung vor Versand ist nicht grün – Versand gesperrt.")
        c = self.konfig["claude"]
        antwort = claude_auftrag.senden(self.auftrag_anonym, self.dokument_anonym or None, modell=c["modell"],
                                        effort=c["effort"], max_tokens=c["max_tokens"], client=client)
        self.antwort_anonym = antwort.text
        protokollieren({"vorgang": self.vorgang_id, "schritt": "claude", "modell": antwort.modell,
                        "eingabe_tokens": antwort.eingabe_tokens, "ausgabe_tokens": antwort.ausgabe_tokens})
        return antwort.text

    # 4. Zurück
    def zurueck(self, antwort_anonym: str | None = None) -> Pruefbericht:
        if antwort_anonym is not None:
            self.antwort_anonym = antwort_anonym
        eingang = self.auftrag_anonym + "\n" + self.dokument_anonym
        self.ergebnis, self.bericht_nachher = pruefung.nach_antwort(eingang, self.antwort_anonym, self.zuordnung())
        protokollieren({"vorgang": self.vorgang_id, "schritt": "rueck", "gruen": self.bericht_nachher.gruen,
                        "meldungen": [f"{m.stufe}:{m.pruefung}" for m in self.bericht_nachher.meldungen]})
        return self.bericht_nachher

    def ergebnis_speichern(self, ordner: Path, endung: str = ".docx") -> Path:
        ordner.mkdir(parents=True, exist_ok=True)
        stamm = Path(self.dateiname).stem if self.dateiname else "Entwurf"
        return speichern(self.ergebnis, ordner / f"{stamm}_bearbeitet_{self.vorgang_id or 'ohne-id'}{endung}", stamm)

    def anonyme_docx_speichern(self, ziel: Path) -> Pruefbericht:
        """DOCX formatgetreu anonymisieren (z. B. zur Weitergabe) + Leck-Scan über das gesamte XML."""
        if not self.quelle or self.quelle.suffix.lower() != ".docx":
            raise ValueError("Formatgetreue Ausgabe nur für DOCX-Quellen.")
        a = self.anonymisierer

        def ersetzungen(text: str):
            return [(f.start, f.ende, a.platzhalter_fuer(f.typ, f.wert)) for f in a.funde(text)]

        dok = docx_anonymisieren(self.quelle, ziel, ersetzungen)
        b = Pruefbericht()
        if dok.text() != self.dokument_anonym:
            b.fehler("DOCX", "Text der anonymen DOCX weicht vom geprüften anonymen Text ab.")
        b.anhaengen(pruefung.leck_scan(dok.volltext_xml(), self.zuordnung(), self.typen()))
        return b
