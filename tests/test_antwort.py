"""Rückweg: tolerante Platzhalter, erfundene Platzhalter, neue Namen."""

from vertrags_anonymisierer.harness import pruefung
from vertrags_anonymisierer.rueck.deanonym import einsetzen

ZU = {"[VORNAME_1]": "Hans-Peter", "[NACHNAME_1]": "Müller", "[NACHNAME_1_B]": "MÜLLER", "[STRASSE_1]": "Hauptstraße 5a"}


def test_verstuemmelte_platzhalter_werden_korrigiert():
    text, b = einsetzen("[Vorname 1] [NACHNAME-1], [ nachname_1_b ], [Straße_1], [NACHNAME_1]s Haus", ZU)
    assert text == "Hans-Peter Müller, MÜLLER, Hauptstraße 5a, Müllers Haus"
    assert b.gruen
    assert any("toleriert" in m.text for m in b.meldungen)


def test_unbekannte_platzhalter_sind_rot_und_bleiben_stehen():
    text, b = einsetzen("[VORNAME_1] verkauft an [NACHNAME_7] und [NAME_2].", ZU)
    assert text == "Hans-Peter verkauft an [NACHNAME_7] und [NAME_2]."
    assert not b.gruen


def test_unbekannte_variante_faellt_auf_grundform_zurueck():
    text, b = einsetzen("[NACHNAME_1_C]", ZU)
    assert text == "Müller" and b.gruen and b.meldungen[0].stufe == "WARNUNG"


def test_fremde_eckige_klammern_bleiben_unberuehrt():
    text, b = einsetzen("Siehe [Anlage 1] und [§ 3].", ZU)
    assert text == "Siehe [Anlage 1] und [§ 3]." and b.gruen and not b.meldungen


def test_neue_namen_von_claude_werden_gemeldet():
    _, b = pruefung.nach_antwort("[VORNAME_1] [NACHNAME_1]", "Bürge ist Herr Max Mustermann.", ZU)
    assert any(m.pruefung == "Neue Daten" and "Mustermann" in m.text for m in b.meldungen)


def test_platzhalter_ohne_klammern_wird_gewarnt():
    _, b = einsetzen("Es unterschreibt NACHNAME_1.", ZU)
    assert any(m.stufe == "WARNUNG" for m in b.meldungen)
