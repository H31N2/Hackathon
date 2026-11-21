"""Gesamtablauf mit Claude-Attrappe, Tresor, Kommandozeile und Weboberfläche."""

import pytest
from fastapi.testclient import TestClient

from vertrags_anonymisierer import konfig
from vertrags_anonymisierer.oberflaeche.web import app_erstellen
from vertrags_anonymisierer.platzhalter.tresor import Tresor
from vertrags_anonymisierer.vorgang import Vorgang

from .conftest import KORPUS, FalscherClaude


def test_ganzer_ablauf(falscher_claude, tmp_path, korpus):
    v = Vorgang(konfig.laden())
    v.laden(KORPUS / "kaufvertrag.txt", "Prüfe den Vertrag für Herrn Müller.")
    assert v.vorbereiten().gruen
    tresor = Tresor()
    vid = v.im_tresor_ablegen(tresor)
    v.an_claude(client=falscher_claude)
    gesendet = falscher_claude.anfragen[0]
    nachricht = gesendet["messages"][0]["content"]
    for geheim in ("Müller", "Hans-Peter", "Hauptstraße", "DE89", "Schmidt", "Weber"):
        assert geheim not in nachricht and geheim not in gesendet["system"]
    assert gesendet["model"] == "claude-opus-5-5" and gesendet["thinking"] == {"type": "adaptive"}
    bericht = v.zurueck()
    assert bericht.gruen, [str(m) for m in bericht.meldungen]
    # Die Attrappe gibt das Dokument (mit verstümmelten Platzhaltern) zurück -> muss exakt dem Original entsprechen.
    assert v.ergebnis == "# Überarbeitung\n\n" + korpus["kaufvertrag"]
    ziel = v.ergebnis_speichern(tmp_path)
    assert ziel.exists() and ziel.suffix == ".docx"
    assert tresor.laden(vid) == v.zuordnung()


def test_versand_gesperrt_wenn_rot(falscher_claude):
    v = Vorgang(konfig.laden())
    v.laden(None, "Herr Müller")
    v.vorbereiten()
    v.bericht_vorher.fehler("Test", "rot")
    with pytest.raises(RuntimeError):
        v.an_claude(client=falscher_claude)
    assert not falscher_claude.anfragen


def test_tresor_verschluesselt(datenordner):
    t = Tresor()
    vid = t.speichern({"[NACHNAME_1]": "Müller"}, "x")
    roh = (datenordner / "tresor.db").read_bytes()
    assert "Müller".encode() not in roh and b"M\xc3\xbcller" not in roh
    assert t.laden(vid) == {"[NACHNAME_1]": "Müller"}


def test_weboberflaeche(korpus):
    claude = FalscherClaude(umbau=lambda t: t.replace("[NACHNAME_1]", "[NACHNAME_9]"))
    client = TestClient(app_erstellen(konfig.laden(), client=claude))
    assert "Vertrags-Anonymisierer" in client.get("/").text
    with open(KORPUS / "vollmacht.txt", "rb") as f:
        d = client.post("/api/laden", data={"auftrag": "Prüfen"}, files={"datei": ("vollmacht.txt", f, "text/plain")}).json()
    sid = d["sid"]
    assert d["bericht"]["gruen"] and "Thomas" not in d["dokument_anonym"]
    d = client.post("/api/ergaenzen", data={"sid": sid, "typ": "FIRMA", "wert": "Volksbank"}).json()
    assert "[FIRMA_1]" in d["dokument_anonym"]
    d = client.post("/api/senden", data={"sid": sid}).json()
    assert not d["bericht"]["gruen"]  # [NACHNAME_9] erfunden -> rot
    assert "[NACHNAME_9]" in d["ergebnis"]
    r = client.get(f"/api/download/{sid}")
    assert r.status_code == 200 and r.content[:2] == b"PK"
    d = client.post("/api/zurueck", data={"sid": sid, "antwort": "Herr [Nachname 1] unterschreibt."}).json()
    assert d["ergebnis"] == "Herr Becker unterschreibt." and d["bericht"]["gruen"]
