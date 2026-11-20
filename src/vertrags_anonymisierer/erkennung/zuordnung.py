"""Zuordnung von Schreibvarianten zur selben Person/Sache.

Zwei Stufen:
1. Normalisierung (immer): Groß/klein, Umlaute (ä/ae), Bindestrich/Leerzeichen,
   Titel, Abkürzungen ("Str." = "Straße"). Gleicher Schlüssel = gleiche Nummer.
2. EmbeddingGemma (optional, lokal): fasst Gruppen zusammen, deren Vektoren sehr
   ähnlich sind UND deren Schreibweise sich deutlich überschneidet
   (z. B. "Müller Bau GmbH" und "Müller Bau GmbH & Co. KG").
   Zusammenführungen gelten als unsicher und erscheinen in der Prüfansicht.

Für die Rückanonymisierung ist die Zuordnung unkritisch: Jede Schreibweise
bekommt einen eigenen Platzhalter ([NACHNAME_1], [NACHNAME_1_B]) und wird exakt
zurückgesetzt. Die Zuordnung bestimmt nur, welche Nummer Claude sieht.
"""

from __future__ import annotations

import difflib
import json
import logging
import math
import re
import urllib.request
from dataclasses import dataclass, field
from functools import lru_cache

log = logging.getLogger(__name__)

_TITEL = re.compile(r"\b(?:dr|prof|dipl|med|jur|rer|nat|phil|h\.?\s?c)\.?\s*", re.I)
_ABKUERZUNGEN = [(re.compile(r"str\.", re.I), "strasse"), (re.compile(r"\bst\.\s*", re.I), "sankt ")]
EMBEDDING_TYPEN = {"VORNAME", "NACHNAME", "FIRMA", "STRASSE", "ORT", "GEMARKUNG"}


def normalisiere(wert: str) -> str:
    w = wert.casefold()
    for muster, ersatz in _ABKUERZUNGEN:
        w = muster.sub(ersatz, w)
    w = _TITEL.sub("", w)
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss"), ("é", "e"), ("è", "e")):
        w = w.replace(a, b)
    w = re.sub(r"[\s\- ]+", " ", w)
    w = re.sub(r"[^\w ]", "", w)
    return w.strip()


def _cosinus(a: list[float], b: list[float]) -> float:
    za = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return za / (na * nb) if na and nb else 0.0


def _schreibweise_aehnlich(a: str, b: str) -> bool:
    if a in b or b in a:
        return min(len(a), len(b)) >= 4
    ta, tb = set(a.split()), set(b.split())
    if ta and tb and len(ta & tb) / min(len(ta), len(tb)) >= 0.67 and len(ta & tb) >= 2:
        return True
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.9


class EmbeddingBackend:
    name = "aus"

    def vektoren(self, texte: list[str]) -> list[list[float]] | None:
        return None


class OllamaBackend(EmbeddingBackend):
    """EmbeddingGemma über eine lokale Ollama-Installation (ollama pull embeddinggemma)."""

    name = "ollama"

    def __init__(self, modell: str = "embeddinggemma", url: str = "http://127.0.0.1:11434"):
        self.modell, self.url = modell, url.rstrip("/")

    def vektoren(self, texte: list[str]) -> list[list[float]] | None:
        daten = json.dumps({"model": self.modell, "input": texte}).encode()
        anfrage = urllib.request.Request(f"{self.url}/api/embed", data=daten, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(anfrage, timeout=60) as antwort:
                return json.load(antwort)["embeddings"]
        except Exception as fehler:  # Ollama nicht gestartet o. ä.
            log.warning("EmbeddingGemma über Ollama nicht erreichbar (%s) – nur Normalisierung.", fehler)
            return None


class SentenceTransformersBackend(EmbeddingBackend):
    """EmbeddingGemma direkt über sentence-transformers (google/embeddinggemma-300m)."""

    name = "sentence-transformers"

    def __init__(self, modell: str = "google/embeddinggemma-300m"):
        self.modell = modell

    def vektoren(self, texte: list[str]) -> list[list[float]] | None:
        st = _st_modell(self.modell)
        if st is None:
            return None
        return [list(map(float, v)) for v in st.encode(texte, normalize_embeddings=True)]


@lru_cache(maxsize=1)
def _st_modell(name: str):
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore

        return SentenceTransformer(name)
    except Exception as fehler:
        log.warning("EmbeddingGemma (%s) nicht ladbar (%s) – nur Normalisierung.", name, fehler)
        return None


def backend_aus_konfig(konfig: dict) -> EmbeddingBackend:
    art = konfig.get("backend", "aus")
    if art == "ollama":
        return OllamaBackend(konfig.get("modell", "embeddinggemma"), konfig.get("url", "http://127.0.0.1:11434"))
    if art == "sentence-transformers":
        return SentenceTransformersBackend(konfig.get("modell", "google/embeddinggemma-300m"))
    return EmbeddingBackend()


@dataclass
class Gruppe:
    typ: str
    werte: list[str] = field(default_factory=list)  # erste Schreibweise = Grundform
    schluessel: str = ""
    zusammengefuehrt_von: list[str] = field(default_factory=list)  # durch Embedding


def gruppiere(werte: list[tuple[str, str]], backend: EmbeddingBackend, schwelle: float = 0.9) -> list[Gruppe]:
    """werte: (typ, wert) in Reihenfolge des ersten Auftretens."""
    gruppen: list[Gruppe] = []
    index: dict[tuple[str, str], Gruppe] = {}
    for typ, wert in werte:
        key = (typ, normalisiere(wert))
        g = index.get(key)
        if g is None:
            g = Gruppe(typ, schluessel=key[1])
            index[key] = g
            gruppen.append(g)
        if wert not in g.werte:
            g.werte.append(wert)

    for typ in EMBEDDING_TYPEN:
        kandidaten = [g for g in gruppen if g.typ == typ]
        if len(kandidaten) < 2:
            continue
        vektoren = backend.vektoren([g.werte[0] for g in kandidaten])
        if not vektoren:
            continue
        for j in range(1, len(kandidaten)):
            for i in range(j):
                gi, gj = kandidaten[i], kandidaten[j]
                if gi not in gruppen or gj not in gruppen:
                    continue
                if _cosinus(vektoren[i], vektoren[j]) >= schwelle and _schreibweise_aehnlich(gi.schluessel, gj.schluessel):
                    gi.werte.extend(w for w in gj.werte if w not in gi.werte)
                    gi.zusammengefuehrt_von.append(gj.werte[0])
                    gruppen.remove(gj)
                    break
    return gruppen
