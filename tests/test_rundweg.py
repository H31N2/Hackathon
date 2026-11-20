"""Kernversprechen: anonymisieren -> zurück ist bytegleich, und nichts leckt."""

import pytest

from vertrags_anonymisierer.harness import pruefung
from vertrags_anonymisierer.platzhalter.ersetzen import Anonymisierer, PlatzhalterKollision, einsetzen_strikt


def _lauf(*texte):
    a = Anonymisierer()
    a.analysiere(*texte)
    a.baue_zuordnung(*texte)
    zu = {p: e.wert for p, e in a.zuordnung.items()}
    ty = {p: e.typ for p, e in a.zuordnung.items()}
    return a, zu, ty


def test_round_trip_und_kein_leck_im_korpus(korpus):
    for name, text in korpus.items():
        a, zu, ty = _lauf(text)
        anonym = a.anonymisiere(text)
        assert einsetzen_strikt(anonym, zu) == text, name
        bericht = pruefung.vor_versand([(text, anonym)], zu, ty)
        assert bericht.gruen, (name, [str(m) for m in bericht.meldungen])


def test_kaufvertrag_erwartete_platzhalter(korpus):
    text = korpus["kaufvertrag"]
    a, zu, _ = _lauf(text)
    anonym = a.anonymisiere(text)
    for original in ["Müller", "Hans-Peter", "Weber", "Schmidt", "Heide", "Hauptstraße 5a", "50667",
                     "12.03.1961", "L01X00T47", "DE89 3704 0044 0532 0130 00", "4711", "345/6",
                     "Müller Bau GmbH", "e.vonderheide@example.de", "12 345 678 901", "MÜLLER", "1234/2026"]:
        assert original not in anonym, original
    # Gleiche Person -> gleiche Nummer, Großschreibung als Variante.
    assert "Herr [VORNAME_2] [NACHNAME_2]" in anonym
    assert "Frau [VORNAME_3] [NACHNAME_2] geb. [NACHNAME_3]" in anonym
    assert "[VORNAME_2_B] [NACHNAME_2_B]" in anonym
    assert zu["[NACHNAME_2_B]"] == "MÜLLER"
    # Genitiv bleibt außerhalb des Platzhalters.
    assert "Herrn [NACHNAME_2]s Anteil" in anonym
    # Nicht personenbezogenes bleibt stehen.
    assert "§ 12 Schlussbestimmungen" in anonym and "485.000,00 EUR" in anonym and "Flur 12" in anonym


def test_auftrag_und_dokument_teilen_nummern(korpus):
    auftrag = "Bitte prüfe, ob Herr Müller allein verfügen darf."
    a, _, _ = _lauf(auftrag, korpus["kaufvertrag"])
    assert a.anonymisiere(auftrag) == "Bitte prüfe, ob Herr [NACHNAME_1] allein verfügen darf."
    assert "Frau [VORNAME_3] [NACHNAME_1]" in a.anonymisiere(korpus["kaufvertrag"])


def test_manuell_ergaenzen_und_ausnehmen():
    text = "Der Hof Weißenburger liegt neben dem Anwesen Weißenburger. Ort ist Köln: 50667 Köln."
    a = Anonymisierer()
    a.analysiere(text)
    a.ergaenze("nachname", "Weißenburger", text)
    a.setze_aktiv("ORT", "Köln", False)
    a.baue_zuordnung(text)
    anonym = a.anonymisiere(text)
    assert anonym == "Der Hof [NACHNAME_1] liegt neben dem Anwesen [NACHNAME_1]. Ort ist Köln: [PLZ_1] Köln."


def test_kollision_mit_platzhalterartigem_text():
    with pytest.raises(PlatzhalterKollision):
        Anonymisierer().analysiere("Siehe [Name 1] im Anhang.")


def test_leck_scan_findet_rest():
    zu = {"[NACHNAME_1]": "Müller", "[IBAN_1]": "DE89 3704 0044 0532 0130 00"}
    ty = {"[NACHNAME_1]": "NACHNAME", "[IBAN_1]": "IBAN"}
    b = pruefung.leck_scan("Herr [NACHNAME_1] und Frau Mueller, Konto DE89370400440532013000", zu, ty)
    assert not b.gruen
    assert len([m for m in b.meldungen if m.stufe == "FEHLER"]) == 2


def test_round_trip_erkennt_abweichung():
    b = pruefung.round_trip("Herr Müller", "Herr [NACHNAME_1]", {"[NACHNAME_1]": "Mueller"})
    assert not b.gruen
