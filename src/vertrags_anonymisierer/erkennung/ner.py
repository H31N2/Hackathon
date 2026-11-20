"""Optionale Namenserkennung mit spaCy (lokal).

Ergänzt die Regeln um Personen, die ohne Anrede und ohne bekannten Vornamen im
Text stehen. Ist spaCy oder das deutsche Modell nicht installiert, liefert das
Modul einfach nichts – die Regeln laufen weiter. NER-Funde gelten als
"unsicher" und werden in der Prüfansicht hervorgehoben.
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache

from ..typen import Fund
from .regeln import STOPPWOERTER, _name_zerlegen

log = logging.getLogger(__name__)


@lru_cache(maxsize=2)
def _laden(modell: str):
    try:
        import spacy  # type: ignore
    except ImportError:
        log.info("spaCy nicht installiert – NER übersprungen.")
        return None
    try:
        return spacy.load(modell, disable=["lemmatizer", "textcat"])
    except OSError:
        log.warning("spaCy-Modell %s fehlt (python -m spacy download %s) – NER übersprungen.", modell, modell)
        return None


def verfuegbar(modell: str = "de_core_news_lg") -> bool:
    return _laden(modell) is not None


def erkenne(text: str, modell: str = "de_core_news_lg") -> list[Fund]:
    nlp = _laden(modell)
    if nlp is None:
        return []
    funde: list[Fund] = []
    # Zeilenweise, damit keine Entität über einen Absatz reicht.
    versatz = 0
    for zeile in text.split("\n"):
        if zeile.strip():
            for ent in nlp(zeile).ents:
                if ent.label_ != "PER":
                    continue
                if not re.search(r"[A-ZÄÖÜ]", ent.text) or ent.text in STOPPWOERTER:
                    continue
                for f in _name_zerlegen(ent.text, versatz + ent.start_char):
                    funde.append(Fund(f.start, f.ende, f.typ, f.wert, "ner", sicher=False))
        versatz += len(zeile) + 1
    return funde
