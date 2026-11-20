"""DOCX formatgetreu, PDF-Text, Ausgabe."""

from docx import Document
from docx.shared import Pt

from vertrags_anonymisierer import konfig
from vertrags_anonymisierer.einlesen.dokument import DocxDokument, text_laden
from vertrags_anonymisierer.rueck.ausgabe import docx_schreiben
from vertrags_anonymisierer.vorgang import Vorgang


def _docx(pfad):
    doc = Document()
    p = doc.add_paragraph("Vor mir erschien Herr Hans-")
    r = p.add_run("Peter Mül")  # Name über mehrere Läufe mit Formatierung verteilt
    r.bold = True
    p.add_run("ler, wohnhaft Hauptstraße 5a, 50667 Köln.")
    t = doc.add_table(rows=1, cols=2)
    t.cell(0, 0).text = "Käuferin"
    t.cell(0, 1).text = "Frau Anna Schmidt"
    doc.sections[0].header.paragraphs[0].text = "UR-Nr. 77/2026 – Müller"
    doc.core_properties.author = "Hans-Peter Müller"
    doc.add_paragraph("Konto: IBAN DE89 3704 0044 0532 0130 00").runs[0].font.size = Pt(9)
    doc.save(pfad)


def test_docx_formatgetreu_und_ohne_lecks(tmp_path):
    quelle, ziel = tmp_path / "vertrag.docx", tmp_path / "anonym.docx"
    _docx(quelle)
    v = Vorgang(konfig.laden())
    v.laden(quelle, "")
    assert v.vorbereiten().gruen
    b = v.anonyme_docx_speichern(ziel)
    assert b.gruen, [str(m) for m in b.meldungen]
    dok = DocxDokument(ziel)
    text = dok.text()
    assert text == v.dokument_anonym
    assert "Müller" not in dok.volltext_xml() and "Anna" not in text
    assert "Herr [VORNAME_1] [NACHNAME_1], wohnhaft [STRASSE_1], [PLZ_1] [ORT_1]." in text
    # Formatierung des ersten betroffenen Laufs bleibt erhalten.
    laeufe = dok.absaetze[0].laeufe
    assert any(r.bold for r in laeufe) or laeufe[0].text.endswith("]")
    assert dok.doc.paragraphs[-1].runs[0].font.size == Pt(9)
    assert dok.doc.core_properties.author == ""


def test_pdf_text(tmp_path):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    pfad = tmp_path / "v.pdf"
    c = canvas.Canvas(str(pfad), pagesize=A4)
    c.drawString(72, 760, "Herr Hans Weber, geboren am 01.01.1970, wohnhaft Ringstrasse 4, 10115 Berlin")
    c.save()
    assert "Hans Weber" in text_laden(pfad)


def test_docx_ausgabe_markdown(tmp_path):
    ziel = tmp_path / "e.docx"
    docx_schreiben("# Kaufvertrag\n\n**§ 1** Gegenstand\n- erster Punkt\nText", ziel)
    doc = Document(ziel)
    assert doc.paragraphs[0].style.name.startswith("Heading")
    assert doc.paragraphs[2].runs[0].bold
    assert doc.paragraphs[3].style.name == "List Bullet"
