"""Ergebnis als DOCX schreiben (Claude liefert Markdown-artigen Text)."""

from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.shared import Pt

_FETT = re.compile(r"\*\*(.+?)\*\*")


def _absatz_mit_fett(absatz, text: str) -> None:
    pos = 0
    for m in _FETT.finditer(text):
        if m.start() > pos:
            absatz.add_run(text[pos:m.start()])
        absatz.add_run(m.group(1)).bold = True
        pos = m.end()
    if pos < len(text):
        absatz.add_run(text[pos:])


def docx_schreiben(text: str, ziel: Path, titel: str | None = None) -> None:
    doc = Document()
    stil = doc.styles["Normal"]
    stil.font.name = "Arial"
    stil.font.size = Pt(11)
    if titel:
        doc.core_properties.title = titel
    for zeile in text.split("\n"):
        roh = zeile.rstrip()
        m = re.match(r"^(#{1,4})\s+(.*)$", roh)
        if m:
            doc.add_heading(m.group(2).strip("* "), level=min(len(m.group(1)), 4))
        elif re.match(r"^\s*[-*•]\s+", roh):
            _absatz_mit_fett(doc.add_paragraph(style="List Bullet"), re.sub(r"^\s*[-*•]\s+", "", roh))
        elif re.fullmatch(r"\s*(-{3,}|\*{3,}|_{3,})\s*", roh):
            doc.add_paragraph()
        else:
            _absatz_mit_fett(doc.add_paragraph(), roh)
    doc.save(str(ziel))


def speichern(text: str, ziel: Path, titel: str | None = None) -> Path:
    ziel = Path(ziel)
    if ziel.suffix.lower() == ".docx":
        docx_schreiben(text, ziel, titel)
    else:
        ziel.write_text(text, encoding="utf-8")
    return ziel
