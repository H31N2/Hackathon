"""Dokumente einlesen (DOCX, PDF, TXT) und DOCX formatgetreu anonymisieren."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator

from docx import Document
from docx.table import Table
from docx.text.hyperlink import Hyperlink
from docx.text.paragraph import Paragraph
from docx.text.run import Run

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


@dataclass
class Absatz:
    absatz: Paragraph
    laeufe: list[Run]

    @property
    def text(self) -> str:
        return "".join(r.text for r in self.laeufe)


def _laeufe(p: Paragraph) -> list[Run]:
    erg: list[Run] = []
    for teil in p.iter_inner_content():
        if isinstance(teil, Run):
            erg.append(teil)
        elif isinstance(teil, Hyperlink):
            erg.extend(teil.runs)
    return erg


def _inhalt(container, gesehen: set) -> Iterator[Absatz]:
    for teil in container.iter_inner_content():
        if isinstance(teil, Paragraph):
            if id(teil._p) not in gesehen:
                gesehen.add(id(teil._p))
                yield Absatz(teil, _laeufe(teil))
        elif isinstance(teil, Table):
            for zeile in teil.rows:
                for zelle in zeile.cells:
                    if id(zelle._tc) in gesehen:  # verbundene Zellen nur einmal
                        continue
                    gesehen.add(id(zelle._tc))
                    yield from _inhalt(zelle, gesehen)


class DocxDokument:
    def __init__(self, pfad: Path):
        self.pfad = Path(pfad)
        self.doc = Document(str(pfad))
        gesehen: set = set()
        self.absaetze: list[Absatz] = list(_inhalt(self.doc, gesehen))
        for abschnitt in self.doc.sections:
            for kopf in (abschnitt.header, abschnitt.first_page_header, abschnitt.even_page_header,
                         abschnitt.footer, abschnitt.first_page_footer, abschnitt.even_page_footer):
                if not kopf.is_linked_to_previous and id(kopf._element) not in gesehen:
                    gesehen.add(id(kopf._element))
                    self.absaetze.extend(_inhalt(kopf, gesehen))

    def text(self) -> str:
        return "\n".join(a.text for a in self.absaetze)

    def ersetzen(self, funde: list[tuple[int, int, str]]) -> None:
        """funde: (start, ende, ersatz) bezogen auf self.text(), ohne Überlappung."""
        versatz = 0
        grenzen = []
        for a in self.absaetze:
            grenzen.append((versatz, versatz + len(a.text), a))
            versatz += len(a.text) + 1
        for start, ende, ersatz in sorted(funde, reverse=True):
            for a_start, a_ende, absatz in grenzen:
                if a_start <= start and ende <= a_ende:
                    _in_laeufen_ersetzen(absatz.laeufe, start - a_start, ende - a_start, ersatz)
                    break
            else:
                raise ValueError(f"Fundstelle {start}-{ende} reicht über eine Absatzgrenze")

    def metadaten_leeren(self) -> None:
        cp = self.doc.core_properties
        cp.author = cp.last_modified_by = ""
        cp.title = cp.subject = cp.keywords = cp.comments = ""

    def volltext_xml(self) -> str:
        """Alle w:t-Texte aller Teile (auch Kommentare, Fußnoten, Änderungen) für den Leck-Scan."""
        texte = []
        for teil in self.doc.part.package.iter_parts():
            if teil.content_type.endswith("+xml") and hasattr(teil, "_element"):
                texte.extend(t.text or "" for t in teil._element.iter(f"{W_NS}t"))
                texte.extend(t.text or "" for t in teil._element.iter(f"{W_NS}delText"))
        cp = self.doc.core_properties
        texte += [cp.author or "", cp.last_modified_by or "", cp.title or "", cp.subject or ""]
        return "\n".join(texte)

    def speichern(self, ziel: Path) -> None:
        self.doc.save(str(ziel))


def _in_laeufen_ersetzen(laeufe: list[Run], start: int, ende: int, ersatz: str) -> None:
    pos = 0
    erster = True
    for lauf in laeufe:
        t = lauf.text
        l_start, l_ende = pos, pos + len(t)
        pos = l_ende
        if l_ende <= start or l_start >= ende:
            continue
        a = max(start, l_start) - l_start
        b = min(ende, l_ende) - l_start
        if erster:
            lauf.text = t[:a] + ersatz + t[b:]
            erster = False
        else:
            lauf.text = t[:a] + t[b:]


def pdf_text(pfad: Path) -> str:
    import pdfplumber

    seiten = []
    with pdfplumber.open(str(pfad)) as pdf:
        for seite in pdf.pages:
            seiten.append(seite.extract_text() or "")
    text = "\n".join(seiten)
    if len(re.sub(r"\s", "", text)) < 20:
        raise ValueError("Die PDF enthält kaum Text – vermutlich ein Scan. Bitte zuerst eine Text-PDF oder DOCX erzeugen.")
    return text


def text_laden(pfad: Path) -> str:
    pfad = Path(pfad)
    endung = pfad.suffix.lower()
    if endung == ".docx":
        return DocxDokument(pfad).text()
    if endung == ".pdf":
        return pdf_text(pfad)
    if endung in {".txt", ".md"}:
        return pfad.read_text(encoding="utf-8").replace("\r\n", "\n")
    raise ValueError(f"Dateiformat {endung} wird nicht unterstützt (DOCX, PDF, TXT, MD).")


def docx_anonymisieren(quelle: Path, ziel: Path, platzhalter: Callable[[str], list[tuple[int, int, str]]]) -> DocxDokument:
    """platzhalter: Funktion text -> [(start, ende, ersatz)]."""
    dok = DocxDokument(quelle)
    dok.ersetzen(platzhalter(dok.text()))
    dok.metadaten_leeren()
    dok.speichern(ziel)
    return dok
