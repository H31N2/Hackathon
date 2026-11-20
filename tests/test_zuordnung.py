"""Zuordnung von Schreibvarianten (Normalisierung + EmbeddingGemma-Schnittstelle)."""

from vertrags_anonymisierer.erkennung.zuordnung import EmbeddingBackend, OllamaBackend, gruppiere, normalisiere
from vertrags_anonymisierer.platzhalter.ersetzen import Anonymisierer


class FesteVektoren(EmbeddingBackend):
    """Steht für EmbeddingGemma: ähnliche Firmennamen bekommen fast gleiche Vektoren."""

    name = "test"

    def vektoren(self, texte):
        return [[1.0, 0.05 * len(t) % 1, 0.0] if "Müller Bau" in t else [0.0, 0.0, 1.0] for t in texte]


def test_normalisierung():
    assert normalisiere("Hauptstr. 5") == normalisiere("Hauptstraße 5")
    assert normalisiere("Hans-Peter") == normalisiere("Hans Peter") == normalisiere("HANS PETER")
    assert normalisiere("Müller") == normalisiere("Mueller")


def test_embedding_fuehrt_firmenvarianten_zusammen():
    werte = [("FIRMA", "Müller Bau GmbH"), ("FIRMA", "Müller Bau GmbH & Co. KG"), ("FIRMA", "Schulz AG")]
    gruppen = gruppiere(werte, FesteVektoren(), 0.9)
    assert [g.werte for g in gruppen] == [["Müller Bau GmbH", "Müller Bau GmbH & Co. KG"], ["Schulz AG"]]
    assert gruppen[0].zusammengefuehrt_von == ["Müller Bau GmbH & Co. KG"]


def test_aehnliche_aber_verschiedene_namen_bleiben_getrennt():
    class Alles(EmbeddingBackend):
        def vektoren(self, texte):
            return [[1.0, 0.0] for _ in texte]

    gruppen = gruppiere([("NACHNAME", "Müller"), ("NACHNAME", "Möller")], Alles(), 0.9)
    assert len(gruppen) == 2


def test_varianten_bekommen_gleiche_nummer_und_exakten_rueckweg():
    text = "Die Müller Bau GmbH & Co. KG (vormals Müller Bau GmbH) zahlt an die Schulz AG."
    a = Anonymisierer(FesteVektoren())
    a.analysiere(text)
    a.baue_zuordnung(text)
    anonym = a.anonymisiere(text)
    assert anonym == "Die [FIRMA_1] (vormals [FIRMA_1_B]) zahlt an die [FIRMA_2]."


def test_ollama_nicht_erreichbar_ist_kein_fehler():
    assert OllamaBackend(url="http://127.0.0.1:9").vektoren(["x"]) is None
